import re

import pytest
from sqlmodel import Session

from app.auth import routes
from app.auth.ports import GitHubIdentity, GoogleIdentity
from app.auth.service import EmailCodes, SessionError, TooSoon, user_for_email, user_for_github, user_for_google
from app.core.db import engine


class FakeMailer:
    def __init__(self, works: bool = True) -> None:
        self.works = works
        self.sent: list[tuple[str, str, str]] = []

    @property
    def enabled(self) -> bool:
        return True

    async def send(self, to: str, subject: str, body: str) -> bool:
        self.sent.append((to, subject, body))
        return self.works


@pytest.fixture
def mailer(monkeypatch):
    fake = FakeMailer()
    monkeypatch.setattr(routes, "mailer", fake)
    monkeypatch.setattr(routes, "email_codes", EmailCodes())
    return fake


def _code(mailer: FakeMailer) -> str:
    return re.search(r"\d{6}", mailer.sent[-1][1]).group()


def test_email_code_signs_in_and_makes_the_account(app_client, mailer):
    client = app_client()
    assert client.get("/api/auth/me").json()["email_enabled"] is True
    resp = client.post("/api/auth/email/start", json={"email": " New@Example.com ", "lang": "zh"})
    assert resp.status_code == 200 and resp.json()["expires_in"] == 600
    to, subject, body = mailer.sent[-1]
    assert to == "new@example.com" and "验证码" in subject and _code(mailer) in body
    resp = client.post("/api/auth/email/verify", json={"email": "new@example.com", "code": _code(mailer)})
    assert resp.status_code == 200 and resp.json()["email"] == "new@example.com"
    assert client.get("/api/auth/me").json()["user"]["email"] == "new@example.com"


def test_a_code_works_once(app_client, mailer):
    client = app_client()
    client.post("/api/auth/email/start", json={"email": "once@example.com"})
    code = _code(mailer)
    assert client.post("/api/auth/email/verify", json={"email": "once@example.com", "code": code}).status_code == 200
    assert app_client().post("/api/auth/email/verify", json={"email": "once@example.com", "code": code}).status_code == 400


def test_five_wrong_tries_use_the_code_up(app_client, mailer):
    client = app_client()
    client.post("/api/auth/email/start", json={"email": "guess@example.com"})
    code = _code(mailer)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        resp = client.post("/api/auth/email/verify", json={"email": "guess@example.com", "code": wrong})
        assert resp.status_code == 400  # not 401: a typo mustn't feed fail2ban
    assert client.post("/api/auth/email/verify", json={"email": "guess@example.com", "code": code}).status_code == 400


def test_a_code_is_for_its_own_address(app_client, mailer):
    client = app_client()
    client.post("/api/auth/email/start", json={"email": "mine@example.com"})
    resp = client.post("/api/auth/email/verify", json={"email": "other@example.com", "code": _code(mailer)})
    assert resp.status_code == 400


def test_sending_is_limited(app_client, mailer):
    client = app_client()
    assert client.post("/api/auth/email/start", json={"email": "flood@example.com"}).status_code == 200
    assert client.post("/api/auth/email/start", json={"email": "flood@example.com"}).status_code == 429
    assert len(mailer.sent) == 1


def test_per_visitor_and_daily_limits():
    codes = EmailCodes()
    for i in range(10):
        codes.issue(f"a{i}@example.com", "1.2.3.4")
    with pytest.raises(TooSoon):
        codes.issue("a10@example.com", "1.2.3.4")
    for i in range(80):
        codes.issue(f"b{i}@example.com", f"ip{i}")
    with pytest.raises(TooSoon):  # 90 a day, whoever asks
        codes.issue("c@example.com", "5.6.7.8")


def test_a_mail_that_did_not_go_out_leaves_no_code(app_client, mailer):
    mailer.works = False
    client = app_client()
    assert client.post("/api/auth/email/start", json={"email": "down@example.com"}).status_code == 502
    code = _code(mailer)
    assert client.post("/api/auth/email/verify", json={"email": "down@example.com", "code": code}).status_code == 400


def test_not_an_email(app_client, mailer):
    for bad in ("nobody", "a@b", "a b@c.com", "x" * 250 + "@example.com"):
        assert app_client().post("/api/auth/email/start", json={"email": bad}).status_code == 422
    assert mailer.sent == []


def test_email_sign_in_is_off_without_a_mail_service(app_client):
    client = app_client()
    assert client.get("/api/auth/me").json()["email_enabled"] is False
    assert client.post("/api/auth/email/start", json={"email": "x@example.com"}).status_code == 503


def test_one_account_whichever_way_in():
    with Session(engine) as db:
        by_mail = user_for_email(db, "Both@Example.com")
        by_github = user_for_github(db, GitHubIdentity(id="42", email="both@example.com", name="Both"))
        by_google = user_for_google(db, GoogleIdentity(sub="g-both", email="both@example.com", email_verified=True, name="B"))
        assert by_mail.id == by_github.id == by_google.id
        assert by_github.github_id == "42"
        assert user_for_github(db, GitHubIdentity(id="42", email="changed@example.com", name="")).id == by_mail.id


def test_github_without_a_verified_email_is_refused():
    with Session(engine) as db, pytest.raises(SessionError):
        user_for_github(db, GitHubIdentity(id="7", email="", name="x"))


def test_an_email_already_tied_to_another_github_user_is_refused():
    with Session(engine) as db:
        user_for_github(db, GitHubIdentity(id="100", email="taken@example.com", name="a"))
        with pytest.raises(SessionError):
            user_for_github(db, GitHubIdentity(id="101", email="taken@example.com", name="b"))


def test_github_owner_email_becomes_admin():
    with Session(engine) as db:
        assert user_for_github(db, GitHubIdentity(id="900", email="owner@example.com", name="o")).role == "admin"
