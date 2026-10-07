from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.deps import current_user
from app.auth.models import User
from app.core.db import get_session
from app.preferences.schemas import PreferencesResponse, PreferencesUpdate
from app.preferences.service import get_preferences, update_preferences

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesResponse)
def read_preferences(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return PreferencesResponse.model_validate(get_preferences(session, user.id), from_attributes=True)


@router.put("", response_model=PreferencesResponse)
def write_preferences(patch: PreferencesUpdate, user: User = Depends(current_user), session: Session = Depends(get_session)):
    return PreferencesResponse.model_validate(update_preferences(session, user.id, patch), from_attributes=True)
