import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass

from sqlmodel import Session

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.core.db import engine
from app.core.one_time_states import OneTimeStates
from app.spotify.models import SpotifyApp, SpotifyToken
from app.spotify.ports import NowPlaying, SpotifyAuthError, SpotifyClientPort, SpotifyCredentials, TokenBundle

log = logging.getLogger(__name__)

IDLE_POLL_SECONDS = 15.0  # slower cadence while nothing is playing
ERROR_BACKOFF_SECONDS = 15.0
REJECTED_RETRY_SECONDS = 2.0  # after Spotify refuses an unexpired access token
# A poller outlives its last viewer briefly, so a page reload or a car's flaky
# connection re-attaching doesn't restart polling from cold.
POLLER_GRACE_SECONDS = 60.0

REDIRECT_URI = f"{settings.public_base_url}/api/spotify/callback"


# --- Per-user Spotify app + token storage --------------------------------------------


@dataclass
class SpotifyStatus:
    app_configured: bool
    client_id: str
    connected: bool


class SpotifyAccounts:
    """Each user's own Spotify app credentials and OAuth tokens, encrypted at rest.
    Opens its own DB sessions because the pollers run outside any request."""

    def status(self, user_id: int) -> SpotifyStatus:
        with Session(engine) as db:
            app = db.get(SpotifyApp, user_id)
            token = db.get(SpotifyToken, user_id)
        return SpotifyStatus(app is not None, app.client_id if app else "", token is not None)

    def credentials(self, user_id: int) -> SpotifyCredentials | None:
        with Session(engine) as db:
            app = db.get(SpotifyApp, user_id)
        return SpotifyCredentials(app.client_id, decrypt(app.client_secret_enc)) if app else None

    def save_app(self, user_id: int, client_id: str, client_secret: str) -> None:
        """A different client id means a different app: the old token belongs to the
        old app and can't be refreshed with the new one, so it goes."""
        with Session(engine) as db:
            app = db.get(SpotifyApp, user_id)
            if app is not None and app.client_id != client_id:
                token = db.get(SpotifyToken, user_id)
                if token is not None:
                    db.delete(token)
            app = app or SpotifyApp(user_id=user_id, client_id=client_id, client_secret_enc="")
            app.client_id = client_id
            app.client_secret_enc = encrypt(client_secret)
            db.add(app)
            db.commit()

    def remove_app(self, user_id: int) -> None:
        with Session(engine) as db:
            for row in (db.get(SpotifyToken, user_id), db.get(SpotifyApp, user_id)):
                if row is not None:
                    db.delete(row)
            db.commit()

    def load_token(self, user_id: int) -> tuple[str, str, float] | None:
        with Session(engine) as db:
            row = db.get(SpotifyToken, user_id)
        if row is None:
            return None
        return decrypt(row.access_token_enc), decrypt(row.refresh_token_enc), row.expires_at

    def save_token(self, user_id: int, bundle: TokenBundle) -> None:
        with Session(engine) as db:
            row = db.get(SpotifyToken, user_id) or SpotifyToken(user_id=user_id, access_token_enc="", refresh_token_enc="", expires_at=0)
            row.access_token_enc = encrypt(bundle.access_token)
            row.refresh_token_enc = encrypt(bundle.refresh_token)
            row.expires_at = time.time() + bundle.expires_in
            db.add(row)
            db.commit()

    def expire_token(self, user_id: int) -> None:
        with Session(engine) as db:
            row = db.get(SpotifyToken, user_id)
            if row is not None:
                row.expires_at = 0
                db.add(row)
                db.commit()

    def drop_token(self, user_id: int) -> None:
        with Session(engine) as db:
            row = db.get(SpotifyToken, user_id)
            if row is not None:
                db.delete(row)
                db.commit()


# --- Live now-playing: one poller per user, only while someone watches -------------

# Broadcast sentinels besides NowPlaying snapshots:
DISCONNECTED = "disconnected"  # the Spotify link is dead; the user has to reconnect
RESUBSCRIBE = "resubscribe"  # this poller was replaced; streams end and EventSource reconnects


class Broadcaster:
    """Fan-out of one user's latest snapshot to each of their open screens."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self.latest: NowPlaying | str | None = None

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        if self.latest is not None:
            queue.put_nowait(self.latest)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, state: NowPlaying | str) -> None:
        self.latest = state
        for queue in self._subscribers:
            if queue.full():
                queue.get_nowait()  # drop stale snapshot, keep only the newest
            queue.put_nowait(state)


class UserPoller:
    def __init__(self, user_id: int, client: SpotifyClientPort, accounts: SpotifyAccounts) -> None:
        self.user_id = user_id
        self.broadcaster = Broadcaster()
        self._client = client
        self._accounts = accounts
        self.task: asyncio.Task | None = None

    async def _access_token(self, creds: SpotifyCredentials) -> str | None:
        stored = self._accounts.load_token(self.user_id)
        if stored is None:
            return None
        access, refresh, expires_at = stored
        if expires_at - time.time() > 30:
            return access
        bundle = await self._client.refresh(creds, refresh)
        self._accounts.save_token(self.user_id, bundle)
        return bundle.access_token

    async def run(self) -> None:
        idle_since: float | None = None
        while True:
            if self.broadcaster.subscriber_count == 0:
                idle_since = idle_since or time.monotonic()
                if time.monotonic() - idle_since > POLLER_GRACE_SECONDS:
                    return
            else:
                idle_since = None
            try:
                creds = self._accounts.credentials(self.user_id)
                access_token = await self._access_token(creds) if creds else None
                if access_token is None:
                    self.broadcaster.publish(DISCONNECTED)
                    return
                try:
                    state = await self._client.get_currently_playing(access_token)
                except SpotifyAuthError:
                    # Access token refused before its expiry: force a refresh next turn.
                    # A refresh Spotify refuses too is final (handled below).
                    self._accounts.expire_token(self.user_id)
                    await asyncio.sleep(REJECTED_RETRY_SECONDS)
                    continue
                if state is not None:
                    self.broadcaster.publish(state)
                await asyncio.sleep(settings.poll_interval_seconds if state and state.is_playing else IDLE_POLL_SECONDS)
            except asyncio.CancelledError:
                raise
            except SpotifyAuthError:
                # Only the token endpoint gets here: revoked access, rotated secret,
                # deleted app. Drop the token so the UI asks to reconnect.
                log.warning("spotify refresh for user %s refused; dropping token", self.user_id)
                self._accounts.drop_token(self.user_id)
                self.broadcaster.publish(DISCONNECTED)
                return
            except Exception:
                # Transient Spotify/network hiccup — back off and keep polling.
                log.exception("now-playing poll failed for user %s", self.user_id)
                await asyncio.sleep(ERROR_BACKOFF_SECONDS)


class PollerRegistry:
    """User id → poller. A poller starts with its user's first open screen and stops
    POLLER_GRACE_SECONDS after the last one closes, so idle accounts cost nothing.
    Each user's polling counts against their own Spotify app's rate limit."""

    def __init__(self, client: SpotifyClientPort, accounts: SpotifyAccounts) -> None:
        self._client = client
        self._accounts = accounts
        self._pollers: dict[int, UserPoller] = {}

    def subscribe(self, user_id: int) -> tuple[UserPoller, asyncio.Queue]:
        poller = self._pollers.get(user_id)
        if poller is None or poller.task is None or poller.task.done():
            poller = UserPoller(user_id, self._client, self._accounts)
            self._pollers[user_id] = poller
        queue = poller.broadcaster.subscribe()
        if poller.task is None:
            poller.task = asyncio.create_task(poller.run())
        return poller, queue

    def snapshot(self) -> list[tuple[int, int]]:
        """(user id, open screens) for every poller that is running right now."""
        return [(uid, p.broadcaster.subscriber_count) for uid, p in self._pollers.items() if p.task and not p.task.done()]

    def restart(self, user_id: int) -> None:
        """After the user (re)links Spotify or changes their app: open screens are
        reattached to a fresh poller on their next reconnect."""
        poller = self._pollers.pop(user_id, None)
        if poller and poller.task:
            poller.task.cancel()
        if poller:
            poller.broadcaster.publish(RESUBSCRIBE)

    async def stop_all(self) -> None:
        for poller in self._pollers.values():
            if poller.task:
                poller.task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await poller.task
        self._pollers.clear()


# User id travels through Spotify's consent screen inside the single-use state.
pending_states: OneTimeStates[int] = OneTimeStates()
