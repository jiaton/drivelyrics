from sqlmodel import Session

from app.auth.models import User
from app.core.db import engine, init_db
from app.preferences.models import UserPreferences
from app.preferences.service import get_preferences


def test_first_read_survives_a_concurrent_first_read(monkeypatch):
    """Two first requests at once: the slower one's insert fails — it must return the
    row the other created, not a 500."""
    init_db()
    with Session(engine) as db:
        db.add(User(id=31337, email="race@example.com", created_at=0))
        db.add(UserPreferences(user_id=31337, sync_offset_ms=250))  # "the other request" won
        db.commit()
    with Session(engine) as db:
        real_get = db.get
        calls = []

        def stale_first_get(model, key):
            calls.append(key)
            return None if len(calls) == 1 else real_get(model, key)  # it read before the other committed

        monkeypatch.setattr(db, "get", stale_first_get)
        prefs = get_preferences(db, 31337)
        assert prefs.sync_offset_ms == 250
