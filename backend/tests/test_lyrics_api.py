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


def test_search_is_rate_limited_per_user(app_client, monkeypatch):
    monkeypatch.setattr(routes, "service", LyricsService([RomanizingSource("lrclib", romanized=False)]))
    a, b = app_client(), app_client()
    sign_in(a, "search-a@example.com")
    sign_in(b, "search-b@example.com")
    first = a.get("/api/lyrics/search", params={"q": "Song"})
    assert first.status_code == 200 and first.json()["results"][0]["song_id"] == "s1"
    assert a.get("/api/lyrics/search", params={"q": "Song"}).status_code == 429
    assert b.get("/api/lyrics/search", params={"q": "Song"}).status_code == 200  # per user


def test_song_ids_are_validated(app_client):
    a = app_client()
    sign_in(a, "song-id@example.com")
    assert a.get("/api/lyrics/song", params={"source": "lrclib", "song_id": "../x"}).status_code == 422


def test_two_camps_voting_leave_bystanders_with_the_guess(app_client, monkeypatch):
    monkeypatch.setattr(routes, "service", LyricsService([RomanizingSource("lrclib", romanized=False)]))
    a, b, c = app_client(), app_client(), app_client()
    for client, email in ((a, "camp-a@example.com"), (b, "camp-b@example.com"), (c, "bystander@example.com")):
        sign_in(client, email)
    track = {**TRACK, "track_id": "contested"}
    assert a.put("/api/lyrics/cantonese", json={**track, "cantonese": True}).json()["cantonese"] is True
    assert b.put("/api/lyrics/cantonese", json={**track, "cantonese": False}).json()["cantonese"] is False
    assert a.get("/api/lyrics", params=track).json()["cantonese"] is True  # each keeps their own
    assert c.get("/api/lyrics", params=track).json()["cantonese"] is False  # 1 : 1 → the guess
