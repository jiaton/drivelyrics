import hashlib
import secrets
import time

from sqlmodel import Session, select

from app.auth.models import AuthSession, User
from app.auth.ports import GitHubIdentity, GoogleIdentity
from app.core.config import settings

COOKIE_NAME = "lyric_session"
# Sessions never expire server-side; the cookie is what a browser might drop. Chrome
# caps cookie lifetime at 400 days, so the cookie is re-issued (another 400 days) once
# a day while it's in use — a car that opens the app at least once a year stays
# signed in for good. Logging out is the only way a session ends.
COOKIE_MAX_AGE = 400 * 86_400
COOKIE_REFRESH_AFTER = 86_400


class SessionError(Exception):
    pass


class AccountConflict(SessionError):
    """The email's account is already linked to a different account at the provider."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user_id: int, via: str, user_agent: str = "") -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    db.add(AuthSession(token_hash=_hash(token), user_id=user_id, created_at=now, last_seen_at=now, via=via, user_agent=user_agent[:200]))
    db.commit()
    return token


def resolve_session(db: Session, token: str) -> tuple[User, bool] | None:
    """The session's user, and whether the cookie is due to be re-issued."""
    row = db.get(AuthSession, _hash(token))
    if row is None:
        return None
    user = db.get(User, row.user_id)
    if user is None:
        return None
    now = time.time()
    refresh = now - row.last_seen_at > COOKIE_REFRESH_AFTER
    if refresh:
        row.last_seen_at = now
        db.add(row)
        db.commit()
    return user, refresh


def delete_session(db: Session, token: str) -> None:
    row = db.get(AuthSession, _hash(token))
    if row is not None:
        db.delete(row)
        db.commit()


def session_id(row: AuthSession) -> str:
    """What the account page calls a session: a prefix of its token's hash (never the
    token), enough to tell one apart and to sign it out."""
    return row.token_hash[:16]


def session_id_of_token(token: str) -> str:
    return _hash(token)[:16] if token else ""


def list_sessions(db: Session, user_id: int) -> list[AuthSession]:
    rows = db.exec(select(AuthSession).where(AuthSession.user_id == user_id)).all()
    return sorted(rows, key=lambda r: r.last_seen_at, reverse=True)


def delete_user_session(db: Session, user_id: int, sid: str) -> bool:
    for row in list_sessions(db, user_id):
        if session_id(row) == sid:
            db.delete(row)
            db.commit()
            return True
    return False


def delete_all_sessions(db: Session, user_id: int) -> int:
    rows = list_sessions(db, user_id)
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)


def describe_device(user_agent: str) -> str:
    """A short name for a browser from its user agent ("Tesla browser", "Chrome on
    Windows"); "" when it says nothing useful."""
    ua = user_agent or ""
    if "Tesla" in ua:
        return "Tesla browser"
    browser = next(
        (name for key, name in (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("CriOS/", "Chrome"),
                                ("Chrome/", "Chrome"), ("Safari/", "Safari")) if key in ua),
        "",
    )
    system = next(
        (name for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"),
                                ("Mac OS X", "Mac"), ("CrOS", "ChromeOS"), ("Linux", "Linux")) if key in ua),
        "",
    )
    if browser and system:
        return f"{browser} on {system}"
    return browser or system


def prune_dead_sessions(db: Session) -> int:
    """Sessions unused for longer than the cookie lives: no browser can present them
    any more. Keeps the table from only ever growing (one row per sign-in/device)."""
    dead = db.exec(select(AuthSession).where(AuthSession.last_seen_at < time.time() - COOKIE_MAX_AGE)).all()
    for row in dead:
        db.delete(row)
    db.commit()
    return len(dead)


def delete_user(db: Session, user_id: int) -> None:
    """The auth side of account deletion: every session, then the user row. Other
    domains' rows go first (app/account/service.py) — they reference users.id."""
    for row in db.exec(select(AuthSession).where(AuthSession.user_id == user_id)):
        db.delete(row)
    user = db.get(User, user_id)
    if user is not None:
        db.delete(user)
    db.commit()


def _role_for(email: str) -> str:
    return "admin" if settings.owner_email and email == settings.owner_email.strip().lower() else "user"


def user_for_google(db: Session, identity: GoogleIdentity) -> User:
    """Same Google account → same user. A pre-created row (the migrated owner) is
    claimed by verified email on its first sign-in."""
    if not identity.email or not identity.email_verified:
        raise SessionError("Google account has no verified email")
    email = identity.email.strip().lower()
    user = db.exec(select(User).where(User.google_sub == identity.sub)).first()
    if user is None:
        user = db.exec(select(User).where(User.email == email)).first()
        if user is not None and user.google_sub is not None:
            raise AccountConflict("email belongs to an account linked to another Google account")
    if user is None:
        user = User(email=email, role=_role_for(email), created_at=time.time())
    if user.email != email and db.exec(select(User).where(User.email == email, User.id != user.id)).first():
        raise AccountConflict("the Google account's new email belongs to another account")
    user.google_sub = identity.sub
    user.email = email
    user.name = identity.name
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def user_for_github(db: Session, identity: GitHubIdentity) -> User:
    """Same GitHub account → same user; otherwise the account with that verified
    email (whichever way it signed in before) gets GitHub as another way in."""
    if not identity.email:
        raise SessionError("GitHub account has no verified primary email")
    email = identity.email.strip().lower()
    user = db.exec(select(User).where(User.github_id == identity.id)).first()
    if user is None:
        user = db.exec(select(User).where(User.email == email)).first()
        if user is not None and user.github_id is not None:
            raise AccountConflict("email belongs to an account linked to another GitHub user")
    if user is None:
        user = User(email=email, name=identity.name, role=_role_for(email), created_at=time.time())
    user.github_id = identity.id
    if not user.name:
        user.name = identity.name
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def user_for_email(db: Session, email: str) -> User:
    """Signed in by a code sent to the email: the account with that email, or a new one."""
    email = email.strip().lower()
    user = db.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email, name=email.split("@")[0], role=_role_for(email), created_at=time.time())
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def user_for_dev_login(db: Session, email: str) -> User:
    email = email.strip().lower()
    user = db.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email, name=email.split("@")[0], role=_role_for(email), created_at=time.time())
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
