import hashlib
import secrets
import time
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.auth.models import AuthSession, User
from app.auth.ports import GoogleIdentity
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
        user = db.exec(select(User).where(User.email == email, User.google_sub == None)).first()  # noqa: E711
    if user is None:
        user = User(email=email, role=_role_for(email), created_at=time.time())
    user.google_sub = identity.sub
    user.email = email
    user.name = identity.name
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


# --- Device pairing -----------------------------------------------------------------
# The car shows a QR code (and the same short code as text); a phone that's already
# signed in opens it and approves; the car, polling with a secret only it holds, then
# receives its own session cookie. Nothing is typed in the car and Google sign-in never
# runs in the car's browser.

PAIR_TTL_SECONDS = 600
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I lookalikes
_CODE_LENGTH = 6
_MAX_PENDING_PAIRINGS = 500


@dataclass
class _Pairing:
    code: str
    poll_secret_hash: str
    created_at: float
    approved_user_id: int | None = None
    user_agent: str = ""


@dataclass
class PairingRegistry:
    _by_code: dict[str, _Pairing] = field(default_factory=dict)

    def start(self, user_agent: str = "") -> tuple[str, str]:
        """Returns (code, poll_secret). The code is public (it's on screen); the poll
        secret never leaves the requesting browser."""
        self._prune()
        while len(self._by_code) >= _MAX_PENDING_PAIRINGS:
            del self._by_code[next(iter(self._by_code))]
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        poll_secret = secrets.token_urlsafe(32)
        self._by_code[code] = _Pairing(code, _hash(poll_secret), time.time(), user_agent=user_agent[:200])
        return code, poll_secret

    def approve(self, code: str, user_id: int) -> bool:
        self._prune()
        pairing = self._by_code.get(normalize_code(code))
        if pairing is None or pairing.approved_user_id is not None:
            return False
        pairing.approved_user_id = user_id
        return True

    def poll(self, poll_secret: str) -> tuple[str, int | None, str]:
        """("pending" | "approved" | "expired", user_id, user_agent). Approval is handed
        out once; the pairing is gone after that."""
        self._prune()
        wanted = _hash(poll_secret)
        for code, pairing in self._by_code.items():
            if secrets.compare_digest(pairing.poll_secret_hash, wanted):
                if pairing.approved_user_id is None:
                    return "pending", None, ""
                del self._by_code[code]
                return "approved", pairing.approved_user_id, pairing.user_agent
        return "expired", None, ""

    def _prune(self) -> None:
        now = time.time()
        for code in [c for c, p in self._by_code.items() if now - p.created_at > PAIR_TTL_SECONDS]:
            del self._by_code[code]


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


pairings = PairingRegistry()
