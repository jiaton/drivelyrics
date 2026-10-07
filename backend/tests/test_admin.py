from sqlmodel import Session

from app.auth.models import User
from app.core.db import engine
from app.lyrics.models import TrackMatch
from tests.conftest import sign_in


def test_stats_are_admin_only(app_client):
    anonymous, user = app_client(), app_client()
    assert anonymous.get("/api/admin/stats").status_code == 401
    sign_in(user, "not-admin@example.com")
    assert user.get("/api/admin/stats").status_code == 403


def test_stats_for_the_owner(app_client):
    owner = app_client()
    sign_in(owner, "owner@example.com")  # OWNER_EMAIL in conftest → admin
    with Session(engine) as db:
        db.add(TrackMatch(spotify_track_id="nf-1", source="netease", title="Lost", artist="Nobody", source_song_id="", match_version=3, updated_at=5))
        db.add(TrackMatch(spotify_track_id="nf-1", source="lrclib", title="Lost", artist="Nobody", source_song_id="", match_version=3, updated_at=6))
        db.add(TrackMatch(spotify_track_id="ok-1", source="netease", title="Found", artist="Someone", source_song_id="9", match_version=3, manual=True, chosen_by=None, updated_at=7))
        db.commit()

    body = owner.get("/api/admin/stats").json()

    assert body["db_bytes"] > 0
    assert {t["name"] for t in body["tables"]} >= {"users", "trackmatch", "lyricstext", "usertracksource"}
    assert any(u["email"] == "owner@example.com" and u["role"] == "admin" for u in body["users"])
    assert [r["title"] for r in body["not_found"]][:1] == ["Lost"]
    assert any(r["title"] == "Found" for r in body["recent_picks"])
    netease = next(s for s in body["sources"] if s["source"] == "netease")
    assert netease["corrections"] >= 1 and netease["tracks_not_found"] >= 1
