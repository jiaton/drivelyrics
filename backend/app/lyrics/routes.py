from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.auth.deps import current_user
from app.auth.models import User
from app.core.config import settings
from app.core.db import get_session
from app.lyrics.adapter import LrclibClient, NeteaseLyricsClient
from app.lyrics.schemas import CandidateSchema, CandidatesResponse, ChoiceRequest, LyricsResponse
from app.lyrics.service import LyricsResult, LyricsService, NoSyncedLyrics, TrackInfo, UnknownSource, reader_order
from app.preferences.service import get_preferences

router = APIRouter(prefix="/api/lyrics", tags=["lyrics"])
service = LyricsService(([NeteaseLyricsClient()] if settings.netease_api_base_url else []) + [LrclibClient()])


def _track(track_id: str = Query(...), title: str = Query(...), artist: str = Query(...), duration_ms: int | None = Query(None)) -> TrackInfo:
    return TrackInfo(track_id, title, artist, duration_ms)


def _order(session: Session, user: User, track: TrackInfo) -> list[str]:
    prefs = get_preferences(session, user.id)
    return reader_order(session, user.id, track, prefs.lyrics_source, prefs.show_translation)


def _response(result: LyricsResult) -> LyricsResponse:
    return LyricsResponse(
        lines=result.lines, translation_lines=result.translation_lines, source=result.source, song_id=result.song_id, manual=result.manual
    )


@router.get("", response_model=LyricsResponse)
async def get_lyrics(track: TrackInfo = Depends(_track), user: User = Depends(current_user), session: Session = Depends(get_session)):
    return _response(await service.get_lyrics(session, track, _order(session, user, track)))


@router.get("/candidates", response_model=CandidatesResponse)
async def get_candidates(track: TrackInfo = Depends(_track), user: User = Depends(current_user), session: Session = Depends(get_session)):
    shown = await service.get_lyrics(session, track, _order(session, user, track))  # cached: cheap
    selected = (shown.source, shown.song_id)
    return CandidatesResponse(
        candidates=[
            CandidateSchema(
                source=c.candidate.source,
                song_id=c.candidate.song_id,
                name=c.candidate.name,
                artists=c.candidate.artists,
                album=c.candidate.album,
                duration_ms=c.candidate.duration_ms,
                score=round(c.score, 2),
                selected=(c.candidate.source, c.candidate.song_id) == selected,
            )
            for c in await service.candidates(track)
        ]
    )


@router.post("/choice", response_model=LyricsResponse)
async def choose(body: ChoiceRequest, user: User = Depends(current_user), session: Session = Depends(get_session)):
    track = TrackInfo(body.track_id, body.title, body.artist, body.duration_ms)
    try:
        result = await service.choose(session, track, body.source, body.song_id, user.id, body.wrong_source)
    except UnknownSource:
        raise HTTPException(status_code=400, detail="unknown lyrics source")
    except NoSyncedLyrics:
        raise HTTPException(status_code=422, detail="that song has no synced lyrics")
    return _response(result)
