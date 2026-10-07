from sqlmodel import Session

from app.preferences.models import UserPreferences
from app.preferences.schemas import PreferencesUpdate


def get_preferences(session: Session, user_id: int) -> UserPreferences:
    prefs = session.get(UserPreferences, user_id)
    if prefs is None:
        prefs = UserPreferences(user_id=user_id)
        session.add(prefs)
        session.commit()
        session.refresh(prefs)
    return prefs


def update_preferences(session: Session, user_id: int, patch: PreferencesUpdate) -> UserPreferences:
    prefs = get_preferences(session, user_id)
    for field, value in patch.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(prefs, field, value)
    session.add(prefs)
    session.commit()
    session.refresh(prefs)
    return prefs


def delete_preferences(session: Session, user_id: int) -> None:
    prefs = session.get(UserPreferences, user_id)
    if prefs is not None:
        session.delete(prefs)
        session.commit()
