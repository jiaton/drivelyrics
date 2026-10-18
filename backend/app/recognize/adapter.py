"""AudD (audd.io). Two requests on the same audio, in parallel, because no single one
gives both things needed (measured 2026-10-17 on 36 clips):
- the enterprise endpoint with accurate_offsets: where in the recording the match ended
  (end_offset, ms) next to the song's timecode (whole seconds) — the position at the
  start of the recording is timecode − end_offset, within ±0.5 s. The standard
  endpoint's timecode alone points sometimes at the start, sometimes at the end of the
  recording (4 s apart for a 6 s clip) and can't tell which.
- the standard endpoint with return=spotify,apple_music,deezer,musicbrainz: the
  original-script title (AudD's own title for 七里香 is "Chi Li Shiang"), the duration
  and the Spotify id. Spotify is missing for some matches (a compilation album), so
  MusicBrainz and Deezer back it up.
Each counts as one request against the user's key."""

import asyncio
import unicodedata

import httpx

from app.recognize.ports import Alternative, Recognition, RecognizerError, RecognizerKeyRejected, RecognizerPort

STANDARD_URL = "https://api.audd.io/"
ENTERPRISE_URL = "https://enterprise.audd.io/"
TIMEOUT_SECONDS = 20.0
# AudD error codes meaning the key itself is the problem (docs.audd.io: 900 invalid
# api_token, 901 no api_token / out of free requests, 902 limit reached).
_KEY_ERRORS = {900, 901, 902}


def _seconds(timecode: str) -> int:
    parts = [int(p) for p in timecode.split(":")]
    total = 0
    for part in parts:
        total = total * 60 + part
    return total


def _key(s: str | None) -> str:
    return unicodedata.normalize("NFKC", s or "").casefold().strip()


def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and _key(a) == _key(b)


class AuddRecognizer(RecognizerPort):
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def _post(self, client: httpx.AsyncClient, url: str, token: str, audio: bytes, filename: str, extra: dict) -> dict:
        resp = await client.post(url, data={"api_token": token, **extra}, files={"file": (filename, audio)})
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") == "error":
            error = body.get("error") or {}
            if error.get("error_code") in _KEY_ERRORS:
                raise RecognizerKeyRejected(str(error.get("error_message") or "AudD refused the key"))
            raise RecognizerError(str(error.get("error_message") or "AudD failed"))
        return body

    async def recognize(self, token: str, audio: bytes, filename: str, clip_ms: int) -> Recognition | None:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
            standard, enterprise = await asyncio.gather(
                self._post(client, STANDARD_URL, token, audio, filename, {"return": "spotify,apple_music,deezer,musicbrainz"}),
                self._post(client, ENTERPRISE_URL, token, audio, filename, {"accurate_offsets": "true"}),
                return_exceptions=True,
            )
        for result in (standard, enterprise):
            if isinstance(result, RecognizerKeyRejected):
                raise result
        if isinstance(standard, BaseException) and isinstance(enterprise, BaseException):
            raise RecognizerError("AudD is unreachable") from standard
        song = standard.get("result") if isinstance(standard, dict) else None
        precise = [s for chunk in (enterprise.get("result") or []) for s in chunk.get("songs") or []] if isinstance(enterprise, dict) else []
        if not song and not precise:
            return None
        same = [s for s in precise if _same(s.get("title"), song.get("title"))] if song else []
        best = (same or precise or [None])[0]  # the enterprise match of the same song, if it made one

        if best and best.get("timecode") and best.get("end_offset") is not None:
            position_ms, exact = _seconds(best["timecode"]) * 1000 - int(best["end_offset"]), True
        else:
            # Standard timecode only: it marks the start (+1 s) or the end (−1 s) of the
            # recording; short clips point at the end far more often.
            timecode = _seconds(song["timecode"]) * 1000
            position_ms, exact = timecode - (clip_ms - 1000 if clip_ms <= 7000 else 1000), False

        identity = song or best
        spotify = (song or {}).get("spotify") or {}
        apple = (song or {}).get("apple_music") or {}
        deezer = (song or {}).get("deezer") or {}
        brainz = next(iter((song or {}).get("musicbrainz") or []), None) or {}
        title = spotify.get("name") or brainz.get("title") or identity.get("title") or ""
        artist = ", ".join(a.get("name", "") for a in spotify.get("artists") or []) or identity.get("artist") or ""
        duration = spotify.get("duration_ms") or apple.get("durationInMillis") or brainz.get("length") or ((deezer.get("duration") or 0) * 1000)
        album = (spotify.get("album") or {}).get("name") or identity.get("album")
        others = [(song or {}).get("title")] + [s.get("title") for s in precise]
        artists = [(song or {}).get("artist")] + [s.get("artist") for s in precise]
        alternatives: list[Alternative] = []
        seen = {(_key(title), _key(artist))}
        for alt_title, alt_artist in zip(others, artists):
            if alt_title and (_key(alt_title), _key(alt_artist)) not in seen:
                seen.add((_key(alt_title), _key(alt_artist)))
                alternatives.append(Alternative(alt_title, alt_artist or ""))
        return Recognition(
            title, artist, album, int(duration) if duration else None, spotify.get("id"), max(0, position_ms), exact, alternatives[:5]
        )
