from app.lyrics import routes
from app.lyrics.service import LyricsService
from tests.conftest import sign_in
from tests.test_lyrics_service import RomanizingSource

TRACK = {"track_id": "api-track", "title": "Song", "artist": "Artist", "duration_ms": 200000}


def test_jyutping_preference_round_trips(app_client):
    a = app_client()
    sign_in(a, "jp-pref@example.com")
    assert a.get("/api/preferences").json()["show_jyutping"] is False
    assert a.put("/api/preferences", json={"show_jyutping": True}).json()["show_jyutping"] is True


def test_marking_a_track_cantonese_is_shared(app_client, monkeypatch):
    monkeypatch.setattr(routes, "service", LyricsService([RomanizingSource("lrclib", romanized=False)]))
    a, b = app_client(), app_client()
    sign_in(a, "jp-a@example.com")
    sign_in(b, "jp-b@example.com")
    assert a.get("/api/lyrics", params=TRACK).json()["cantonese"] is False

    marked = a.put("/api/lyrics/cantonese", json={**TRACK, "cantonese": True}).json()
    assert marked["cantonese"] and marked["romanization_lines"][0]["text"].startswith("laan4")
    assert b.get("/api/lyrics", params=TRACK).json()["cantonese"] is True
