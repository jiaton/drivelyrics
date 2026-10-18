from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.admin.schemas import StatsResponse
from app.admin.service import collect
from app.auth.deps import current_admin
from app.core.db import get_session
from app.feed.routes import feeds
from app.lyrics.routes import service as lyrics_service
from app.recognize.routes import service as recognize_service
from app.spotify.routes import pollers

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_admin)])


@router.get("/stats", response_model=StatsResponse)
def stats(session: Session = Depends(get_session)):
    counters = dict(lyrics_service.counters) | dict(feeds.counters) | dict(recognize_service.counters)  # both since process start
    return collect(session, pollers.snapshot() + feeds.snapshot(), counters, lyrics_service.counting_since)
