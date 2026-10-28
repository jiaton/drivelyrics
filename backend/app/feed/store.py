"""The feed's persistent state: tokens, settings, monthly usage. Opens its own DB
sessions, like SpotifyAccounts, because the scheduler runs outside any request."""

import hashlib
import secrets
import time
from dataclasses import dataclass

from sqlmodel import Session, select

from app.core.crypto import decrypt, encrypt
from app.core.db import engine
from app.feed.models import FeedSettings, FeedToken, FeedUsage
from app.feed.schemas import FeedSettingsUpdate

TOKEN_PREFIX = "dlf_"
MAX_TOKENS = 10
_TOUCH_EVERY_SECONDS = 60.0  # last_used_at granularity: one write a minute, not per push


class TooManyTokens(Exception):
    pass


@dataclass
class Webhook:
    url: str
    secret: str
    paused: bool


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def month_of(now: float) -> str:
    return time.strftime("%Y-%m", time.gmtime(now))


class FeedStore:
    def create_token(self, user_id: int, name: str) -> tuple[str, FeedToken]:
        with Session(engine) as db:
            if len(db.exec(select(FeedToken.id).where(FeedToken.user_id == user_id)).all()) >= MAX_TOKENS:
                raise TooManyTokens()
            token = TOKEN_PREFIX + secrets.token_urlsafe(32)
            row = FeedToken(user_id=user_id, name=name.strip(), prefix=token[:8], token_hash=_hash(token), created_at=time.time())
            db.add(row)
            db.commit()
            db.refresh(row)
            return token, row

    def tokens(self, user_id: int) -> list[FeedToken]:
        with Session(engine) as db:
            return list(db.exec(select(FeedToken).where(FeedToken.user_id == user_id).order_by(FeedToken.created_at)))

    def has_tokens(self, user_id: int) -> bool:
        with Session(engine) as db:
            return db.exec(select(FeedToken.id).where(FeedToken.user_id == user_id)).first() is not None

    def revoke_token(self, user_id: int, token_id: int) -> bool:
        with Session(engine) as db:
            row = db.get(FeedToken, token_id)
            if row is None or row.user_id != user_id:  # someone else's token: as if absent
                return False
            db.delete(row)
            db.commit()
            return True

    def token_name(self, token: str) -> str | None:
        if not token.startswith(TOKEN_PREFIX):
            return None
        with Session(engine) as db:
            row = db.exec(select(FeedToken).where(FeedToken.token_hash == _hash(token))).first()
            return row.name if row else None

    def user_for_token(self, token: str) -> int | None:
        if not token.startswith(TOKEN_PREFIX):
            return None
        with Session(engine) as db:
            row = db.exec(select(FeedToken).where(FeedToken.token_hash == _hash(token))).first()
            if row is None:
                return None
            now = time.time()
            if row.last_used_at is None or now - row.last_used_at > _TOUCH_EVERY_SECONDS:
                row.last_used_at = now
                db.add(row)
                db.commit()
            return row.user_id

    def settings(self, user_id: int) -> FeedSettings:
        with Session(engine) as db:
            return db.get(FeedSettings, user_id) or FeedSettings(user_id=user_id)

    def update_settings(self, user_id: int, patch: FeedSettingsUpdate) -> FeedSettings:
        with Session(engine) as db:
            row = db.get(FeedSettings, user_id) or FeedSettings(user_id=user_id)
            for field, value in patch.model_dump(exclude_none=True).items():
                setattr(row, field, value)
            db.add(row)
            db.commit()
            db.refresh(row)
            return row

    def webhook(self, user_id: int) -> Webhook | None:
        row = self.settings(user_id)
        if not row.webhook_url_enc:
            return None
        return Webhook(decrypt(row.webhook_url_enc), decrypt(row.webhook_secret_enc), row.webhook_paused)

    def set_webhook(self, user_id: int, url: str) -> str | None:
        """Saves the URL and un-pauses it. Returns a new signing secret if there wasn't
        one yet (shown to the user once), else None (the existing secret stays)."""
        with Session(engine) as db:
            row = db.get(FeedSettings, user_id) or FeedSettings(user_id=user_id)
            new_secret = None
            if not row.webhook_secret_enc:
                new_secret = secrets.token_urlsafe(32)
                row.webhook_secret_enc = encrypt(new_secret)
            row.webhook_url_enc = encrypt(url.strip())
            row.webhook_paused = False
            db.add(row)
            db.commit()
            return new_secret

    def rotate_webhook_secret(self, user_id: int) -> str:
        with Session(engine) as db:
            row = db.get(FeedSettings, user_id) or FeedSettings(user_id=user_id)
            secret = secrets.token_urlsafe(32)
            row.webhook_secret_enc = encrypt(secret)
            db.add(row)
            db.commit()
            return secret

    def clear_webhook(self, user_id: int) -> None:
        with Session(engine) as db:
            row = db.get(FeedSettings, user_id)
            if row is not None:
                row.webhook_url_enc = row.webhook_secret_enc = ""
                row.webhook_paused = False
                db.add(row)
                db.commit()

    def pause_webhook(self, user_id: int) -> None:
        with Session(engine) as db:
            row = db.get(FeedSettings, user_id)
            if row is not None:
                row.webhook_paused = True
                db.add(row)
                db.commit()

    def fetches(self, user_id: int, month: str) -> int:
        with Session(engine) as db:
            row = db.get(FeedUsage, (user_id, month))
            return row.fetches if row else 0

    def count_fetch(self, user_id: int, month: str) -> int:
        with Session(engine) as db:
            row = db.get(FeedUsage, (user_id, month)) or FeedUsage(user_id=user_id, month=month, fetches=0)
            row.fetches += 1
            db.add(row)
            db.commit()
            return row.fetches

    def delete_user(self, user_id: int) -> None:
        with Session(engine) as db:
            for model in (FeedToken, FeedUsage):
                for row in db.exec(select(model).where(model.user_id == user_id)):
                    db.delete(row)
            row = db.get(FeedSettings, user_id)
            if row is not None:
                db.delete(row)
            db.commit()
