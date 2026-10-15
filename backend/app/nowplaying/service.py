"""Which source a user's screens show — their Spotify app or the now-playing feed they
push — and handing each screen's stream to it. The user picks; there's no automatic
switching (owner's decision, 2026-10-15). Reads across spotify/, feed/ and preferences/
on purpose: like account/, it's only the wiring between them."""

import asyncio
from collections.abc import Callable

from sqlmodel import Session

from app.feed.service import FeedRegistry
from app.feed.store import FeedStore
from app.nowplaying.schemas import Source, SourcesResponse
from app.preferences.service import get_preferences
from app.spotify.service import PollerRegistry, SpotifyAccounts


def effective_source(selected: str, spotify_connected: bool, feed_enabled: bool) -> Source | None:
    available: list[Source] = [s for s, ok in (("spotify", spotify_connected), ("feed", feed_enabled)) if ok]
    if not available:
        return None
    return selected if selected in available else available[0]  # type: ignore[return-value]


class NowPlayingSources:
    def __init__(self, accounts: SpotifyAccounts, pollers: PollerRegistry, feed_store: FeedStore, feeds: FeedRegistry) -> None:
        self._accounts = accounts
        self._pollers = pollers
        self._feed_store = feed_store
        self._feeds = feeds

    def info(self, db: Session, user_id: int) -> SourcesResponse:
        selected = get_preferences(db, user_id).now_playing_source
        spotify = self._accounts.status(user_id).connected
        feed = self._feed_store.has_tokens(user_id)
        return SourcesResponse(selected=selected, effective=effective_source(selected, spotify, feed), spotify_connected=spotify, feed_enabled=feed)

    def select(self, db: Session, user_id: int, source: Source) -> SourcesResponse:
        prefs = get_preferences(db, user_id)
        if prefs.now_playing_source != source:
            prefs.now_playing_source = source
            db.add(prefs)
            db.commit()
            # Open screens end their stream and reconnect to the newly chosen source.
            self._pollers.restart(user_id)
            self._feeds.resubscribe(user_id)
        return self.info(db, user_id)

    def subscribe(self, db: Session, user_id: int) -> tuple[Source, asyncio.Queue, Callable[[], None]] | None:
        """(source, queue of snapshots/sentinels, unsubscribe) for one screen, or None
        when the user has no source set up."""
        source = self.info(db, user_id).effective
        if source == "feed":
            feed, queue = self._feeds.subscribe_screen(user_id)
            return source, queue, lambda: feed.screens.unsubscribe(queue)
        if source == "spotify":
            poller, queue = self._pollers.subscribe(user_id)
            return source, queue, lambda: poller.broadcaster.unsubscribe(queue)
        return None
