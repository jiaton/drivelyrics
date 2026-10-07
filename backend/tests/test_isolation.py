from tests.conftest import sign_in

HEX = "0123456789abcdef0123456789abcdef"


def test_preferences_are_per_user(app_client):
    a, b = app_client(), app_client()
    sign_in(a, "iso-a@example.com")
    sign_in(b, "iso-b@example.com")
    a.put("/api/preferences", json={"show_translation": True})
    assert a.get("/api/preferences").json()["show_translation"] is True
    assert b.get("/api/preferences").json()["show_translation"] is False


def test_spotify_app_is_per_user_and_secret_never_returned(app_client):
    a, b = app_client(), app_client()
    sign_in(a, "sp-a@example.com")
    sign_in(b, "sp-b@example.com")
    resp = a.put("/api/spotify/app", json={"client_id": HEX, "client_secret": HEX[::-1]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["app_configured"] and not body["connected"]
    assert body["redirect_uri"] == "http://testserver/api/spotify/callback"
    assert HEX[::-1] not in resp.text
    assert b.get("/api/spotify/status").json()["app_configured"] is False


def test_spotify_app_rejects_malformed_values(app_client):
    a = app_client()
    sign_in(a, "sp-bad@example.com")
    assert a.put("/api/spotify/app", json={"client_id": "nope", "client_secret": HEX}).status_code == 422


def test_spotify_connect_requires_an_app(app_client):
    a = app_client()
    sign_in(a, "sp-none@example.com")
    assert a.get("/api/spotify/connect", follow_redirects=False).status_code == 409


def test_spotify_callback_from_another_browser_is_refused(app_client):
    from app.spotify.service import pending_states

    a, b = app_client(), app_client()
    sign_in(a, "cb-a@example.com")
    sign_in(b, "cb-b@example.com")
    a.put("/api/spotify/app", json={"client_id": HEX, "client_secret": HEX})
    a_id = a.get("/api/auth/me").json()["user"]["id"]
    state = pending_states.issue(a_id)
    resp = b.get(f"/api/spotify/callback?code=x&state={state}", follow_redirects=False)
    assert resp.headers["location"] == "/?spotify=failed"


def test_deleting_an_account_removes_its_data_but_keeps_shared_fixes(app_client):
    from sqlmodel import Session, select

    from app.auth.models import AuthSession, User
    from app.core.db import engine
    from app.lyrics.models import TrackMatch, UserTrackSource
    from app.preferences.models import UserPreferences
    from app.spotify.models import SpotifyApp

    gone, other = app_client(), app_client()
    sign_in(gone, "leaving@example.com")
    sign_in(other, "staying@example.com")
    uid = gone.get("/api/auth/me").json()["user"]["id"]
    gone.put("/api/preferences", json={"show_translation": True})
    gone.put("/api/spotify/app", json={"client_id": HEX, "client_secret": HEX})
    with Session(engine) as db:
        db.add(TrackMatch(spotify_track_id="del-1", source="netease", title="T", artist="A", source_song_id="1", match_version=3, manual=True, chosen_by=uid, updated_at=0))
        db.add(UserTrackSource(user_id=uid, spotify_track_id="del-1", source="netease", updated_at=0))
        db.commit()

    resp = gone.delete("/api/account")

    assert resp.status_code == 200 and "Max-Age=0" in resp.headers["set-cookie"]
    assert gone.get("/api/auth/me").json()["user"] is None
    with Session(engine) as db:
        assert db.get(User, uid) is None
        assert db.exec(select(AuthSession).where(AuthSession.user_id == uid)).first() is None
        assert db.get(SpotifyApp, uid) is None and db.get(UserPreferences, uid) is None
        assert db.get(UserTrackSource, (uid, "del-1")) is None
        fix = db.get(TrackMatch, ("del-1", "netease"))
        assert fix.manual and fix.source_song_id == "1" and fix.chosen_by is None
    assert other.get("/api/auth/me").json()["user"]["email"] == "staying@example.com"


def test_deleting_an_account_with_no_preferences_row(app_client):
    client = app_client()
    sign_in(client, "bare@example.com")
    client.put("/api/spotify/app", json={"client_id": HEX, "client_secret": HEX})
    assert client.delete("/api/account").status_code == 200
    assert client.get("/api/auth/me").json()["user"] is None
