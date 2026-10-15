from dataclasses import dataclass
from typing import Protocol

from app.core.nowplaying import NowPlaying


@dataclass
class SpotifyCredentials:
    """One user's own Spotify Developer app."""

    client_id: str
    client_secret: str


@dataclass
class TokenBundle:
    access_token: str
    refresh_token: str
    expires_in: float  # seconds


class SpotifyAuthError(Exception):
    """Spotify rejected the app credentials or the refresh token (revoked access,
    secret rotated, app deleted). Retrying won't help — the user has to reconnect."""


class SpotifyClientPort(Protocol):
    """Everything the service layer needs from Spotify's OAuth + Web API."""

    def build_authorize_url(self, creds: SpotifyCredentials, state: str, redirect_uri: str) -> str: ...

    async def exchange_code(self, creds: SpotifyCredentials, code: str, redirect_uri: str) -> TokenBundle: ...

    async def refresh(self, creds: SpotifyCredentials, refresh_token: str) -> TokenBundle: ...

    async def get_currently_playing(self, access_token: str) -> NowPlaying | None:
        """Raises SpotifyAuthError when the access token is no longer accepted."""
        ...
