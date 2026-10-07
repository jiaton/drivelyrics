from dataclasses import dataclass
from typing import Protocol

from app.lyrics.matching import Candidate


@dataclass
class RawLyric:
    lrc: str | None
    tlyric: str | None  # translated LRC, if the provider has one


class LyricsSourcePort(Protocol):
    """One external lyrics provider: NetEase (self-hosted sidecar) or LRCLIB."""

    name: str  # stored in TrackMatch.source / LyricsText.source; never rename

    async def search(self, keywords: str) -> list[Candidate]:
        """Raw search hits in the provider's own order, each with source=name.
        Picking one is not the adapter's job — see lyrics/matching.py."""
        ...

    async def fetch_raw_lyric(self, song_id: str) -> RawLyric:
        """Both fields None means the provider has no synced lyrics for this song."""
        ...
