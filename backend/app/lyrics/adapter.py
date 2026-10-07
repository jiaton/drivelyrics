import httpx

from app.core.config import settings
from app.lyrics.matching import Candidate, split_artists
from app.lyrics.ports import LyricsSourcePort, RawLyric


class NeteaseLyricsClient(LyricsSourcePort):
    """Talks to the self-hosted NeteaseCloudMusicApi-compatible sidecar over the
    internal docker network only — never exposed through Caddy."""

    name = "netease"

    def __init__(self) -> None:
        self._base_url = settings.netease_api_base_url

    async def search(self, keywords: str) -> list[Candidate]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10) as client:
            resp = await client.get("/search", params={"keywords": keywords, "type": 1, "limit": 10})
            resp.raise_for_status()
            songs = resp.json().get("result", {}).get("songs") or []
        return [
            Candidate(
                song_id=str(song["id"]),
                name=song.get("name") or "",
                artists=[a.get("name") or "" for a in song.get("artists", [])],
                duration_ms=song.get("duration") or None,
                album=(song.get("album") or {}).get("name"),
                aliases=tuple(song.get("alias") or ()),
                source=self.name,
            )
            for song in songs
        ]

    async def fetch_raw_lyric(self, song_id: str) -> RawLyric:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10) as client:
            resp = await client.get("/lyric", params={"id": song_id})
            resp.raise_for_status()
            body = resp.json()
        return RawLyric(
            lrc=body.get("lrc", {}).get("lyric") or None,
            tlyric=body.get("tlyric", {}).get("lyric") or None,
        )


class LrclibClient(LyricsSourcePort):
    """lrclib.net: free, open, no key, community-synced lyrics with good coverage of
    English-language music (and some Chinese), where NetEase is weakest. Its terms ask
    clients to identify themselves in the User-Agent."""

    name = "lrclib"
    _headers = {"User-Agent": f"lyric ({settings.public_base_url})"}

    async def search(self, keywords: str) -> list[Candidate]:
        async with httpx.AsyncClient(base_url=settings.lrclib_base_url, timeout=10, headers=self._headers) as client:
            resp = await client.get("/api/search", params={"q": keywords})
            resp.raise_for_status()
            hits = resp.json() or []
        return [
            Candidate(
                song_id=str(hit["id"]),
                name=hit.get("trackName") or "",
                artists=split_artists(hit.get("artistName") or ""),
                duration_ms=int(hit["duration"] * 1000) if hit.get("duration") else None,
                album=hit.get("albumName"),
                source=self.name,
            )
            for hit in hits[:10]
            if hit.get("syncedLyrics") and not hit.get("instrumental")  # plain text can't scroll
        ]

    async def fetch_raw_lyric(self, song_id: str) -> RawLyric:
        async with httpx.AsyncClient(base_url=settings.lrclib_base_url, timeout=10, headers=self._headers) as client:
            resp = await client.get(f"/api/get/{song_id}")
            if resp.status_code == 404:
                return RawLyric(lrc=None, tlyric=None)
            resp.raise_for_status()
            body = resp.json()
        return RawLyric(lrc=body.get("syncedLyrics") or None, tlyric=None)
