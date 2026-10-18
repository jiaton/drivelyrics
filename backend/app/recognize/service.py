import logging
import time
from collections import Counter

from sqlmodel import Session

from app.core.crypto import decrypt, encrypt
from app.lyrics.matching import text_track_id
from app.recognize.models import RecognizerKey
from app.recognize.ports import RecognizerPort
from app.recognize.schemas import RecognizedAlternative, RecognizeResponse, RecognizerKeyStatus

log = logging.getLogger(__name__)


class NoKey(Exception):
    pass


def key_status(db: Session, user_id: int) -> RecognizerKeyStatus:
    row = db.get(RecognizerKey, user_id)
    return RecognizerKeyStatus(configured=row is not None, hint=f"…{row.hint}" if row else "")


def save_key(db: Session, user_id: int, token: str) -> RecognizerKeyStatus:
    token = token.strip()
    row = db.get(RecognizerKey, user_id) or RecognizerKey(user_id=user_id, token_enc="", hint="", created_at=time.time())
    row.token_enc, row.hint = encrypt(token), token[-4:]
    db.add(row)
    db.commit()
    return key_status(db, user_id)


def delete_key(db: Session, user_id: int) -> None:
    row = db.get(RecognizerKey, user_id)
    if row is not None:
        db.delete(row)
        db.commit()


class RecognizeService:
    def __init__(self, recognizer: RecognizerPort) -> None:
        self._recognizer = recognizer
        self.counters: Counter[str] = Counter()

    async def recognize(self, db: Session, user_id: int, audio: bytes, filename: str, clip_ms: int) -> RecognizeResponse:
        row = db.get(RecognizerKey, user_id)
        if row is None:
            raise NoKey()
        token = decrypt(row.token_enc)
        db.close()  # don't hold the DB session through two slow network calls
        self.counters["recognize:requests"] += 1
        found = await self._recognizer.recognize(token, audio, filename, clip_ms)
        if found is None:
            return RecognizeResponse(matched=False)
        self.counters["recognize:matches"] += 1
        # Songs only, never who listened: for diagnosing odd matches.
        log.info("recognized %r — %r (spotify %s); alternatives %s", found.title, found.artist, bool(found.spotify_id), [(a.title, a.artist) for a in found.alternatives])
        return RecognizeResponse(
            matched=True,
            title=found.title,
            artist=found.artist,
            album=found.album,
            duration_ms=found.duration_ms,
            track_id=found.spotify_id or text_track_id(found.title, found.artist),
            position_ms=found.position_ms,
            exact=found.exact,
            alternatives=[RecognizedAlternative(title=a.title, artist=a.artist, track_id=text_track_id(a.title, a.artist)) for a in found.alternatives],
        )
