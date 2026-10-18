from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Alternative:
    title: str
    artist: str


@dataclass
class Recognition:
    title: str
    artist: str
    album: str | None
    duration_ms: int | None
    spotify_id: str | None
    position_ms: int  # song position at the start of the recording
    exact: bool
    # Other releases the same audio matched. The same recording is often re-released
    # under another title (a Vietnamese-titled upload of 最美的期待, 2026-10-18), and the
    # first match isn't always the one with lyrics.
    alternatives: list[Alternative] = field(default_factory=list)


class RecognizerKeyRejected(Exception):
    """The provider refused the user's key (wrong, or out of requests)."""


class RecognizerError(Exception):
    """The provider failed for another reason; the message is safe to show."""


class RecognizerPort(Protocol):
    async def recognize(self, token: str, audio: bytes, filename: str, clip_ms: int) -> Recognition | None:
        """None = no song recognized in this audio."""
        ...
