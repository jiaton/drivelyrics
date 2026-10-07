import time
from urllib.parse import urlencode

import httpx

from app.spotify.ports import NowPlaying, SpotifyAuthError, SpotifyClientPort, SpotifyCredentials, TokenBundle

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
CURRENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"

SCOPES = "user-read-currently-playing user-read-playback-state"


class SpotifyApiClient(SpotifyClientPort):
    def build_authorize_url(self, creds: SpotifyCredentials, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": creds.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, creds: SpotifyCredentials, code: str, redirect_uri: str) -> TokenBundle:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                auth=(creds.client_id, creds.client_secret),
            )
            _raise_for_token_status(resp)
            body = resp.json()
        return TokenBundle(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            expires_in=body["expires_in"],
        )

    async def refresh(self, creds: SpotifyCredentials, refresh_token: str) -> TokenBundle:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                auth=(creds.client_id, creds.client_secret),
            )
            _raise_for_token_status(resp)
            body = resp.json()
        return TokenBundle(
            access_token=body["access_token"],
            # Spotify doesn't always return a new refresh_token — keep the old one if so.
            refresh_token=body.get("refresh_token", refresh_token),
            expires_in=body["expires_in"],
        )

    async def get_currently_playing(self, access_token: str) -> NowPlaying | None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                CURRENTLY_PLAYING_URL,
                # Without this Spotify romanizes CJK artist names ("Mayday" for 五月天,
                # "Ronghao Li" for 李荣浩), which NetEase can't match. Titles are
                # unaffected (they stay in their original script either way), and
                # Latin-script artists come back unchanged. Verified 2026-10-03.
                headers={"Authorization": f"Bearer {access_token}", "Accept-Language": "zh-CN"},
                params={"additional_types": "track"},
            )
        if resp.status_code == 401:
            raise SpotifyAuthError("access token rejected")
        if resp.status_code == 204:
            return NowPlaying(
                is_playing=False,
                track_id=None,
                name=None,
                artist=None,
                album_art_url=None,
                duration_ms=None,
                progress_ms=None,
                fetched_at=time.time(),
            )
        resp.raise_for_status()
        body = resp.json()
        item = body.get("item") or {}
        images = item.get("album", {}).get("images") or []
        return NowPlaying(
            is_playing=body.get("is_playing", False),
            track_id=item.get("id"),
            name=item.get("name"),
            artist=", ".join(a["name"] for a in item.get("artists", [])),
            album_art_url=images[0]["url"] if images else None,
            duration_ms=item.get("duration_ms"),
            progress_ms=body.get("progress_ms"),
            fetched_at=time.time(),
        )


def _raise_for_token_status(resp: httpx.Response) -> None:
    # 400 invalid_grant (revoked/expired refresh token or code) and 401 invalid_client
    # (wrong or rotated secret) are permanent; anything else is worth retrying.
    if resp.status_code in (400, 401):
        raise SpotifyAuthError(f"token endpoint answered {resp.status_code}")
    resp.raise_for_status()
