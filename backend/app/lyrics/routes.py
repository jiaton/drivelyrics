from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.auth.deps import current_user
from app.auth.models import User
from app.core.config import settings
from app.core.db import get_session
from app.lyrics.adapter import LrclibClient, NeteaseLyricsClient
from app.core.rate_limit import MinInterval
from app.lyrics.cantonese import vote_cantonese
from app.lyrics.schemas import CandidateSchema, CandidatesResponse, CantoneseRequest, ChoiceRequest, LyricsResponse, SearchHit, SearchResponse
from app.lyrics.order import reader_order, source_order
from app.lyrics.service import LyricsResult, LyricsService, NoSyncedLyrics, ProviderUnavailable, TrackInfo, UnknownSource
from app.preferences.service import get_preferences

router = APIRouter(prefix="/api/lyrics", tags=["lyrics"])
# Each search queries every provider; each song view may fetch from one.
_search_limit = MinInterval(1.0)
_song_limit = MinInterval(0.5)

service = LyricsService(([NeteaseLyricsClient()] if settings.netease_api_base_url else []) + [LrclibClient()])


def _track(track_id: str = Query(...), title: str = Query(...), artist: str = Query(...), duration_ms: int | None = Query(None)) -> TrackInfo:
    return TrackInfo(track_id, title, artist, duration_ms)


def _order(session: Session, user: User, track: TrackInfo) -> list[str]:
    prefs = get_preferences(session, user.id)
    return reader_order(session, user.id, track, prefs.lyrics_source, prefs.show_translation)


def _response(result: LyricsResult) -> LyricsResponse:
    return LyricsResponse(
        lines=result.lines,
        translation_lines=result.translation_lines,
        source=result.source,
        song_id=result.song_id,
        manual=result.manual,
        cantonese=result.cantonese,
        romanization_lines=result.romanization_lines,
    )


@router.get("", response_model=LyricsResponse)
async def get_lyrics(track: TrackInfo = Depends(_track), user: User = Depends(current_user), session: Session = Depends(get_session)):
    return _response(await service.get_lyrics(session, track, _order(session, user, track), user.id))


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


@router.put("/cantonese", response_model=LyricsResponse)
async def set_cantonese(body: CantoneseRequest, user: User = Depends(current_user), session: Session = Depends(get_session)):
    """The reader's vote on whether the track is Cantonese (decides it for them, counts
    once for everyone else); answers with its lyrics as they now see them."""
    track = TrackInfo(body.track_id, body.title, body.artist, body.duration_ms)
    vote_cantonese(session, track.track_id, body.cantonese, user.id)
    return _response(await service.get_lyrics(session, track, _order(session, user, track), user.id))


@router.get("/search", response_model=SearchResponse)
async def search(q: str = Query(min_length=1, max_length=100), user: User = Depends(current_user), session: Session = Depends(get_session)):
    """The search screen: songs matching free text, from every source."""
    if not _search_limit.allow(user.id):
        raise HTTPException(status_code=429, detail="searching too fast")
    query = q.strip()
    prefs = get_preferences(session, user.id)
    order = source_order(TrackInfo("", query, "", None), prefs.lyrics_source, prefs.show_translation)
    hits = await service.search(query, order)
    return SearchResponse(
        results=[SearchHit(source=h.source, song_id=h.song_id, name=h.name, artists=h.artists, album=h.album, duration_ms=h.duration_ms) for h in hits]
    )


@router.get("/song", response_model=LyricsResponse)
async def song(
    source: str = Query(...),
    song_id: str = Query(pattern=r"^\d{1,20}$"),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """One search result's lyrics."""
    if not _song_limit.allow(user.id):
        raise HTTPException(status_code=429, detail="too fast")
    try:
        return _response(await service.song(session, source, song_id))
    except UnknownSource:
        raise HTTPException(status_code=400, detail="unknown lyrics source")
    except NoSyncedLyrics:
        raise HTTPException(status_code=422, detail="that song has no synced lyrics")
    except ProviderUnavailable:
        raise HTTPException(status_code=502, detail="lyrics provider unavailable")
