import httpx
import pytest

from app.recognize import routes
from app.recognize.adapter import AuddRecognizer
from app.recognize.ports import Recognition, RecognizerKeyRejected
from app.recognize.service import RecognizeService
from tests.conftest import sign_in

# Shapes as returned by AudD on 2026-10-17 (七里香, a 6 s clip from 0:45).
STANDARD = {
    "status": "success",
    "result": {
        "artist": "Jay Chou",
        "title": "Chi Li Shiang",
        "album": "Common Jasmine Orange",
        "timecode": "00:50",
        "spotify": {"name": "七里香", "id": "57w29bSwdIZ6gr6xXOqwc1", "duration_ms": 297200, "artists": [{"name": "Jay Chou"}], "album": {"name": "七里香"}},
        "apple_music": {"name": "Qi-Li-Xiang", "durationInMillis": 297200},
    },
}
ENTERPRISE = {"status": "success", "result": [{"songs": [{"title": "Chi Li Shiang", "artist": "Jay Chou", "timecode": "00:50", "start_offset": 1, "end_offset": 5260}]}]}


def transport(standard, enterprise):
    def handler(request: httpx.Request) -> httpx.Response:
        body = enterprise if request.url.host == "enterprise.audd.io" else standard
        return body if isinstance(body, httpx.Response) else httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


async def test_combines_precise_position_with_original_title():
    found = await AuddRecognizer(transport(STANDARD, ENTERPRISE)).recognize("k", b"audio", "clip.webm", 6000)
    assert (found.title, found.artist, found.duration_ms, found.spotify_id) == ("七里香", "Jay Chou", 297200, "57w29bSwdIZ6gr6xXOqwc1")
    assert (found.position_ms, found.exact) == (50_000 - 5260, True)


async def test_estimates_from_the_standard_timecode_when_the_precise_call_fails():
    found = await AuddRecognizer(transport(STANDARD, httpx.Response(500))).recognize("k", b"a", "clip.webm", 6000)
    assert (found.position_ms, found.exact) == (50_000 - 5000, False)  # short clip: timecode ≈ its end − 1 s


async def test_uses_the_precise_match_alone_and_reports_no_match():
    only_precise = await AuddRecognizer(transport({"status": "success", "result": None}, ENTERPRISE)).recognize("k", b"a", "c.webm", 6000)
    assert (only_precise.title, only_precise.exact) == ("Chi Li Shiang", True)
    empty = {"status": "success", "result": None}
    assert await AuddRecognizer(transport(empty, {"status": "success", "result": []})).recognize("k", b"a", "c.webm", 6000) is None


async def test_a_refused_key_is_reported_as_such():
    refused = {"status": "error", "error": {"error_code": 900, "error_message": "Wrong API token"}}
    with pytest.raises(RecognizerKeyRejected):
        await AuddRecognizer(transport(refused, refused)).recognize("bad", b"a", "c.webm", 6000)


class FakeRecognizer:
    def __init__(self, found):
        self.found = found
        self.tokens = []

    async def recognize(self, token, audio, filename, clip_ms):
        self.tokens.append(token)
        return self.found


def test_key_management_and_recognition(app_client, monkeypatch):
    fake = FakeRecognizer(Recognition("七里香", "Jay Chou", None, 297200, "57w29bSwdIZ6gr6xXOqwc1", 44_740, True))
    monkeypatch.setattr(routes, "service", RecognizeService(fake))
    a = app_client()
    sign_in(a, "recognize@example.com")
    clip = {"audio": ("clip.webm", b"x" * 100, "audio/webm")}
    assert a.post("/api/recognize", files=clip, data={"clip_ms": 6000}).status_code == 409  # no key yet
    status = a.put("/api/recognize/key", json={"token": "test0000token0000fake0000000abcd"}).json()
    assert status == {"configured": True, "hint": "…abcd"}
    body = a.post("/api/recognize", files=clip, data={"clip_ms": 6000}).json()
    assert body["matched"] and body["track_id"] == "57w29bSwdIZ6gr6xXOqwc1" and body["position_ms"] == 44_740
    assert fake.tokens == ["test0000token0000fake0000000abcd"]  # decrypted for the call only
    assert a.post("/api/recognize", files=clip, data={"clip_ms": 6000}).status_code == 429
    assert a.delete("/api/recognize/key").status_code == 200
    assert a.get("/api/recognize/key").json()["configured"] is False


def test_recognition_input_is_checked(app_client, monkeypatch):
    monkeypatch.setattr(routes, "service", RecognizeService(FakeRecognizer(None)))
    a = app_client()
    sign_in(a, "recognize-input@example.com")
    a.put("/api/recognize/key", json={"token": "0123456789abcdef0123"})
    assert a.post("/api/recognize", files={"audio": ("x.txt", b"hi", "text/plain")}, data={"clip_ms": 6000}).status_code == 415
    too_big = {"audio": ("c.webm", b"x" * (routes.MAX_AUDIO_BYTES + 1), "audio/webm")}
    assert a.post("/api/recognize", files=too_big, data={"clip_ms": 6000}).status_code == 413
    assert a.post("/api/recognize", files={"audio": ("c.webm", b"x", "audio/webm")}, data={"clip_ms": 999999}).status_code == 422


def test_without_a_spotify_match_the_id_comes_from_title_and_artist(app_client, monkeypatch):
    monkeypatch.setattr(routes, "service", RecognizeService(FakeRecognizer(Recognition("Song", "Band", None, None, None, 1000, True))))
    a = app_client()
    sign_in(a, "recognize-noid@example.com")
    a.put("/api/recognize/key", json={"token": "0123456789abcdef0123"})
    body = a.post("/api/recognize", files={"audio": ("c.webm", b"x", "audio/webm")}, data={"clip_ms": 6000}).json()
    assert body["track_id"].startswith("feed:")


async def test_without_spotify_musicbrainz_and_deezer_fill_in():
    standard = {"status": "success", "result": {"artist": "Jay Chou", "title": "Chi Li Shiang", "timecode": "00:50", "spotify": None,
                "musicbrainz": [{"title": "七里香", "length": 297200}], "deezer": {"title": "Qi-Li-Xiang", "duration": 297}}}
    found = await AuddRecognizer(transport(standard, ENTERPRISE)).recognize("k", b"a", "c.webm", 6000)
    assert (found.title, found.duration_ms, found.spotify_id) == ("七里香", 297200, None)
    deezer_only = {"status": "success", "result": {"artist": "A", "title": "T", "timecode": "00:50", "deezer": {"duration": 200}}}
    assert (await AuddRecognizer(transport(deezer_only, ENTERPRISE)).recognize("k", b"a", "c.webm", 6000)).duration_ms == 200_000
