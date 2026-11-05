"""Pairing limits and the device it shows, Google account conflicts, signing out everywhere."""

import pytest
from sqlmodel import Session

from app.auth import device_routes, routes
from app.auth.ports import GoogleIdentity
from app.auth.service import AccountConflict, describe_device, user_for_google
from app.core.db import engine
from app.core.rate_limit import Window
from tests.conftest import sign_in

TESLA_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36 Tesla/2026.26"


@pytest.fixture(autouse=True)
def fresh_limits(monkeypatch):
    monkeypatch.setattr(device_routes, "pair_starts", Window(30, 3600))
    monkeypatch.setattr(device_routes, "pair_polls", Window(120, 60))
    monkeypatch.setattr(device_routes, "pair_misses", Window(10, 600))


def _google(sub: str, email: str) -> GoogleIdentity:
    return GoogleIdentity(sub=sub, email=email, email_verified=True, name="N")


# --- Google: an email already linked to another Google account -----------------------


def test_google_email_linked_to_another_google_account_is_a_conflict():
    with Session(engine) as db:
        user_for_google(db, _google("sub-first", "dup@example.com"))
        with pytest.raises(AccountConflict):
            user_for_google(db, _google("sub-second", "dup@example.com"))


def test_google_email_change_onto_another_account_is_a_conflict():
    with Session(engine) as db:
        user_for_google(db, _google("sub-a", "a-mail@example.com"))
        user_for_google(db, _google("sub-b", "b-mail@example.com"))
        with pytest.raises(AccountConflict):
            user_for_google(db, _google("sub-a", "b-mail@example.com"))


def test_google_conflict_lands_on_the_sign_in_page_not_a_500(app_client, monkeypatch):
    with Session(engine) as db:
        user_for_google(db, _google("sub-taken", "taken-g@example.com"))

    async def identify(code, redirect_uri):
        return _google("sub-other", "taken-g@example.com")

    monkeypatch.setattr(routes.google, "identify", identify)
    state = routes.oauth_states.issue("/")
    resp = app_client().get(f"/api/auth/google/callback?code=x&state={state}", follow_redirects=False)
    assert resp.status_code in (302, 307) and resp.headers["location"] == "/?signin=conflict"


# --- Pairing: rate limits ---------------------------------------------------------------


def test_pairing_codes_per_visitor_are_limited(app_client, monkeypatch):
    monkeypatch.setattr(device_routes, "pair_starts", Window(3, 3600))
    car = app_client()
    for _ in range(3):
        assert car.post("/api/auth/pair/start").status_code == 200
    assert car.post("/api/auth/pair/start").status_code == 429


def test_polling_is_limited(app_client, monkeypatch):
    monkeypatch.setattr(device_routes, "pair_polls", Window(2, 60))
    car = app_client()
    secret = car.post("/api/auth/pair/start").json()["poll_secret"]
    for _ in range(2):
        assert car.post("/api/auth/pair/poll", json={"poll_secret": secret}).status_code == 200
    assert car.post("/api/auth/pair/poll", json={"poll_secret": secret}).status_code == 429


def test_guessing_codes_is_limited_per_user(app_client):
    car, phone = app_client(), app_client()
    sign_in(phone, "guesser@example.com")
    code = car.post("/api/auth/pair/start").json()["code"]
    for i in range(10):
        assert phone.post("/api/auth/pair/approve", json={"code": f"WRONG{i}"}).status_code == 404
    # Even the right code is refused now, and looking codes up counts the same.
    assert phone.post("/api/auth/pair/approve", json={"code": code}).status_code == 429
    assert phone.get(f"/api/auth/pair/info?code={code}").status_code == 429


def test_wrong_lookups_count_too(app_client):
    phone = app_client()
    sign_in(phone, "looker@example.com")
    for i in range(10):
        assert phone.get(f"/api/auth/pair/info?code=NOPE{i}").status_code == 404
    assert phone.get("/api/auth/pair/info?code=NOPE").status_code == 429


# --- Pairing: the approve page says which device asks -------------------------------------


def test_pair_info_names_the_device_and_where_it_is(app_client):
    car, phone = app_client(), app_client()
    sign_in(phone, "check@example.com")
    code = car.post(
        "/api/auth/pair/start",
        headers={"user-agent": TESLA_UA, "cf-ipcity": "Fremont", "cf-region": "California", "cf-ipcountry": "US"},
    ).json()["code"]
    info = phone.get(f"/api/auth/pair/info?code={code.lower()}").json()
    assert info["device"] == "Tesla browser" and info["location"] == "Fremont, California, US"
    assert info["asked_at"] > 0


def test_pair_info_needs_a_signed_in_phone(app_client):
    car = app_client()
    code = car.post("/api/auth/pair/start").json()["code"]
    assert app_client().get(f"/api/auth/pair/info?code={code}").status_code == 401


def test_device_names():
    assert describe_device(TESLA_UA) == "Tesla browser"
    win = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
    assert describe_device(win) == "Chrome on Windows"
    iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
    assert describe_device(iphone) == "Safari on iPhone"
    assert describe_device("Mozilla/5.0 (Windows NT 10.0) Edg/136.0") == "Edge on Windows"
    assert describe_device("") == ""


# --- Sessions: list, sign one out, sign out everywhere --------------------------------------


def test_session_list_marks_this_one(app_client):
    laptop, car = app_client(), app_client()
    sign_in(laptop, "devices@example.com")
    sign_in(car, "devices@example.com")
    listed = laptop.get("/api/auth/sessions").json()["sessions"]
    assert len(listed) == 2 and sum(s["current"] for s in listed) == 1
    assert all(len(s["id"]) == 16 for s in listed)


def test_sign_out_one_other_session(app_client):
    laptop, car = app_client(), app_client()
    sign_in(laptop, "one@example.com")
    sign_in(car, "one@example.com")
    other = next(s for s in laptop.get("/api/auth/sessions").json()["sessions"] if not s["current"])
    assert laptop.delete(f"/api/auth/sessions/{other['id']}").status_code == 200
    assert car.get("/api/auth/me").json()["user"] is None
    assert laptop.get("/api/auth/me").json()["user"]["email"] == "one@example.com"


def test_cannot_sign_out_someone_elses_session(app_client):
    mine, theirs = app_client(), app_client()
    sign_in(mine, "mine@example.com")
    sign_in(theirs, "theirs@example.com")
    their_id = theirs.get("/api/auth/sessions").json()["sessions"][0]["id"]
    assert mine.delete(f"/api/auth/sessions/{their_id}").status_code == 404
    assert theirs.get("/api/auth/me").json()["user"]["email"] == "theirs@example.com"


def test_sign_out_everywhere(app_client):
    laptop, car, other_user = app_client(), app_client(), app_client()
    sign_in(laptop, "everywhere@example.com")
    sign_in(car, "everywhere@example.com")
    sign_in(other_user, "bystander@example.com")
    resp = laptop.post("/api/auth/logout-everywhere")
    assert resp.status_code == 200 and "Max-Age=0" in resp.headers["set-cookie"]
    assert laptop.get("/api/auth/me").json()["user"] is None
    assert car.get("/api/auth/me").json()["user"] is None
    assert other_user.get("/api/auth/me").json()["user"]["email"] == "bystander@example.com"
