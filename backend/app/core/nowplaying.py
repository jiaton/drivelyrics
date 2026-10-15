"""What a user's screens are shown as "now playing", whichever source it comes from
(their Spotify app, or the now-playing feed they push themselves), and the fan-out of
it to every open screen. Cross-domain plumbing: spotify/ and feed/ both produce it."""

import asyncio
from dataclasses import dataclass


@dataclass
class NowPlaying:
    is_playing: bool
    track_id: str | None
    name: str | None
    artist: str | None
    album_art_url: str | None
    duration_ms: int | None
    progress_ms: int | None
    fetched_at: float  # unix timestamp this snapshot was read at
    source: str = "spotify"  # "spotify" | "feed"


# Broadcast sentinels besides NowPlaying snapshots:
DISCONNECTED = "disconnected"  # the Spotify link is dead; the user has to reconnect
RESUBSCRIBE = "resubscribe"  # the source changed or was replaced; streams end and EventSource reconnects


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
