import asyncio

import pytest

from app.spotify import service as spotify_service
from app.spotify.ports import NowPlaying, SpotifyAuthError, SpotifyCredentials, TokenBundle
from app.spotify.service import DISCONNECTED, RESUBSCRIBE, PollerRegistry


class FakeAccounts:
    def __init__(self, users):
        self.tokens = {u: ("access", "refresh", 9e12) for u in users}
        self.dropped: list[int] = []

    def credentials(self, user_id):
        return SpotifyCredentials("id", "secret") if user_id in self.tokens or user_id in self.dropped else None

    def load_token(self, user_id):
        return self.tokens.get(user_id)

    def save_token(self, user_id, bundle):
        self.tokens[user_id] = (bundle.access_token, bundle.refresh_token, 9e12)

    def expire_token(self, user_id):
        a, r, _ = self.tokens[user_id]
        self.tokens[user_id] = (a, r, 0)

    def drop_token(self, user_id):
        self.tokens.pop(user_id, None)
        self.dropped.append(user_id)


class FakeSpotify:
    def __init__(self):
        self.polls: dict[str, int] = {}
        self.refresh_fails = False
        self.reject_first = False

    async def refresh(self, creds, refresh_token):
        if self.refresh_fails:
            raise SpotifyAuthError("revoked")
        return TokenBundle("access2", refresh_token, 3600)

    async def get_currently_playing(self, access_token):
        self.polls[access_token] = self.polls.get(access_token, 0) + 1
        if self.reject_first and access_token == "access":
            raise SpotifyAuthError("expired early")
        return NowPlaying(True, "t", "Song", "Artist", None, 200_000, 1000, 0.0)


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(spotify_service.settings, "poll_interval_seconds", 0.01)
    monkeypatch.setattr(spotify_service, "IDLE_POLL_SECONDS", 0.01)
    monkeypatch.setattr(spotify_service, "POLLER_GRACE_SECONDS", 0.05)
    monkeypatch.setattr(spotify_service, "ERROR_BACKOFF_SECONDS", 0.01)
    monkeypatch.setattr(spotify_service, "REJECTED_RETRY_SECONDS", 0.01)


async def test_each_user_gets_their_own_stream():
    registry = PollerRegistry(FakeSpotify(), FakeAccounts([1, 2]))
    p1, q1 = registry.subscribe(1)
    p2, q2 = registry.subscribe(2)
    assert p1 is not p2
    assert isinstance(await asyncio.wait_for(q1.get(), 1), NowPlaying)
    assert isinstance(await asyncio.wait_for(q2.get(), 1), NowPlaying)
    second_poller, _ = registry.subscribe(1)
    assert second_poller is p1  # a second screen shares the user's poller
    await registry.stop_all()


async def test_poller_stops_after_the_last_viewer_leaves():
    registry = PollerRegistry(FakeSpotify(), FakeAccounts([1]))
    poller, queue = registry.subscribe(1)
    await asyncio.wait_for(queue.get(), 1)
    poller.broadcaster.unsubscribe(queue)
    await asyncio.wait_for(poller.task, 1)
    again, _ = registry.subscribe(1)
    assert again is not poller and not again.task.done()
    await registry.stop_all()


async def test_refused_refresh_drops_the_link_and_tells_the_screen():
    spotify, accounts = FakeSpotify(), FakeAccounts([1])
    accounts.tokens[1] = ("access", "refresh", 0)  # due for refresh
    spotify.refresh_fails = True
    registry = PollerRegistry(spotify, accounts)
    _, queue = registry.subscribe(1)
    assert await asyncio.wait_for(queue.get(), 1) == DISCONNECTED
    assert accounts.dropped == [1]


async def test_access_token_rejected_early_is_refreshed_not_dropped():
    spotify, accounts = FakeSpotify(), FakeAccounts([1])
    spotify.reject_first = True
    registry = PollerRegistry(spotify, accounts)
    _, queue = registry.subscribe(1)
    assert isinstance(await asyncio.wait_for(queue.get(), 1), NowPlaying)
    assert accounts.tokens[1][0] == "access2" and accounts.dropped == []
    await registry.stop_all()


async def test_restart_ends_open_streams_so_they_reconnect():
    registry = PollerRegistry(FakeSpotify(), FakeAccounts([1]))
    _, queue = registry.subscribe(1)
    await asyncio.wait_for(queue.get(), 1)
    registry.restart(1)
    assert await asyncio.wait_for(queue.get(), 1) == RESUBSCRIBE
