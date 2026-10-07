from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.admin.schemas import StatsResponse
from app.admin.service import collect
from app.auth.deps import current_admin
from app.core.db import get_session
from app.lyrics.routes import service as lyrics_service
from app.spotify.routes import pollers

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_admin)])


@router.get("/stats", response_model=StatsResponse)
def stats(session: Session = Depends(get_session)):
    return collect(session, pollers.snapshot(), dict(lyrics_service.counters), lyrics_service.counting_since)
