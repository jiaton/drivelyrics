import time

from sqlmodel import Session, select

from app.auth.models import AuthSession, User
from app.auth.ports import GoogleIdentity
from app.auth.service import COOKIE_NAME, SessionError, user_for_google
from app.core.db import engine
from tests.conftest import sign_in


def test_signed_out_page_load_is_not_a_401(app_client):
    # fail2ban counts 401s; loading the login screen must not produce one.
    resp = app_client().get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["user"] is None


def test_protected_routes_need_a_session(app_client):
    client = app_client()
    for path in ("/api/preferences", "/api/spotify/status", "/api/lyrics?track_id=x&title=a&artist=b"):
        assert client.get(path).status_code == 401, path


def test_session_cookie_is_long_lived_and_httponly(app_client):
    client = app_client()
    resp = client.post("/api/auth/dev-login", json={"email": "cookie@example.com"})
    header = resp.headers["set-cookie"]
    assert f"{COOKIE_NAME}=" in header and "HttpOnly" in header and "Max-Age=34560000" in header
    assert client.get("/api/auth/me").json()["user"]["email"] == "cookie@example.com"


def test_logout_ends_the_session_server_side(app_client):
    client = app_client()
    sign_in(client, "logout@example.com")
    token = client.cookies.get(COOKIE_NAME)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json()["user"] is None
    other = app_client()
    other.cookies.set(COOKIE_NAME, token)  # a copy of the old cookie is dead too
    assert other.get("/api/auth/me").json()["user"] is None


def test_cookie_is_reissued_once_a_day_while_in_use(app_client):
    client = app_client()
    sign_in(client, "sliding@example.com")
    assert "set-cookie" not in client.get("/api/auth/me").headers  # fresh: no rewrite
    with Session(engine) as db:
        user = db.exec(select(User).where(User.email == "sliding@example.com")).one()
        for row in db.exec(select(AuthSession).where(AuthSession.user_id == user.id)):
            row.last_seen_at = time.time() - 2 * 86_400
            db.add(row)
        db.commit()
    assert "Max-Age=34560000" in client.get("/api/auth/me").headers["set-cookie"]


def test_pairing_signs_the_car_in_as_the_approving_user(app_client):
    car, phone = app_client(), app_client()
    sign_in(phone, "pair@example.com")

    start = car.post("/api/auth/pair/start").json()
    assert start["approve_url"].endswith(f"/pair?code={start['code']}")
    assert start["qr_svg"].startswith("<svg")
    assert car.post("/api/auth/pair/poll", json={"poll_secret": start["poll_secret"]}).json()["status"] == "pending"

    assert phone.post("/api/auth/pair/approve", json={"code": start["code"].lower()}).status_code == 200

    approved = car.post("/api/auth/pair/poll", json={"poll_secret": start["poll_secret"]})
    assert approved.json()["status"] == "approved"
    assert car.get("/api/auth/me").json()["user"]["email"] == "pair@example.com"
    # Handed out once.
    assert car.post("/api/auth/pair/poll", json={"poll_secret": start["poll_secret"]}).json()["status"] == "expired"


def test_pairing_approval_needs_a_signed_in_phone(app_client):
    car, stranger = app_client(), app_client()
    code = car.post("/api/auth/pair/start").json()["code"]
    assert stranger.post("/api/auth/pair/approve", json={"code": code}).status_code == 401


def test_wrong_poll_secret_learns_nothing(app_client):
    car = app_client()
    car.post("/api/auth/pair/start")
    assert car.post("/api/auth/pair/poll", json={"poll_secret": "guess"}).json()["status"] == "expired"


def _identity(sub, email, verified=True):
    return GoogleIdentity(sub=sub, email=email, email_verified=verified, name="N")


def test_google_sign_in_claims_the_pre_created_owner_row():
    with Session(engine) as db:
        db.add(User(email="claim@example.com", role="admin", created_at=0))
        db.commit()
        user = user_for_google(db, _identity("sub-claim", "Claim@Example.com"))
        assert user.role == "admin" and user.google_sub == "sub-claim"
        again = user_for_google(db, _identity("sub-claim", "claim@example.com"))
        assert again.id == user.id


def test_google_owner_email_becomes_admin_on_a_fresh_install():
    with Session(engine) as db:
        assert user_for_google(db, _identity("sub-owner", "owner@example.com")).role == "admin"
        assert user_for_google(db, _identity("sub-friend", "friend@example.com")).role == "user"


def test_unverified_google_email_is_refused():
    with Session(engine) as db:
        try:
            user_for_google(db, _identity("sub-x", "x@example.com", verified=False))
        except SessionError:
            return
    raise AssertionError("expected SessionError")


def test_next_path_cannot_leave_the_site():
    from app.auth.routes import _safe_next

    assert _safe_next("/pair?code=AB") == "/pair?code=AB"
    for bad in ("//evil.com", "https://evil.com", "/\\evil.com", None, ""):
        assert _safe_next(bad) == "/"


def test_handoff_carries_a_session_from_an_old_hostname(app_client):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, base_url="http://lyrics.tjia.dev") as old_host, TestClient(app) as new_host:
        sign_in(old_host, "moving@example.com")
        jump = old_host.get("/api/auth/handoff", follow_redirects=False)
        location = jump.headers["location"]
        assert location.startswith("http://testserver/api/auth/handoff/complete?token=")

        landed = new_host.get(location.replace("http://testserver", ""), follow_redirects=False)
        assert landed.headers["location"] == "/"
        assert new_host.get("/api/auth/me").json()["user"]["email"] == "moving@example.com"

        replay = app_client()  # the token is single-use
        replay.get(location.replace("http://testserver", ""), follow_redirects=False)
        assert replay.get("/api/auth/me").json()["user"] is None


def test_handoff_without_a_session_just_goes_to_the_new_site(app_client):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, base_url="http://lyrics.tjia.dev") as old_host:
        jump = old_host.get("/api/auth/handoff", follow_redirects=False)
        assert jump.headers["location"] == "http://testserver/"
