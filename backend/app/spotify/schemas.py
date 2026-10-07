import re

from pydantic import BaseModel, field_validator

_SPOTIFY_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class SpotifyStatusResponse(BaseModel):
    app_configured: bool
    client_id: str
    connected: bool
    redirect_uri: str  # what the user must register on their Spotify app


class SpotifyAppRequest(BaseModel):
    client_id: str
    client_secret: str

    @field_validator("client_id", "client_secret")
    @classmethod
    def _looks_like_spotify_id(cls, value: str) -> str:
        # Both are 32 lowercase hex chars on the Spotify dashboard; catching a pasted
        # space or the wrong field here beats a vague OAuth error later.
        value = value.strip()
        if not _SPOTIFY_ID_RE.match(value):
            raise ValueError("expected the 32-character value from the Spotify dashboard")
        return value


class NowPlayingResponse(BaseModel):
    is_playing: bool
    track_id: str | None
    name: str | None
    artist: str | None
    album_art_url: str | None
    duration_ms: int | None
    progress_ms: int | None
    fetched_at: float
