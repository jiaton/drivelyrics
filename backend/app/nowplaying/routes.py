import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse

from app.auth.deps import current_user
from app.auth.models import User
from app.core.db import get_session
from app.core.nowplaying import DISCONNECTED, RESUBSCRIBE
from app.feed.deps import bearer_token, feed_user
from app.feed.routes import feeds
from app.feed.schemas import FeedMe
from app.feed.routes import store as feed_store
from app.nowplaying.schemas import SourcesResponse, SourceUpdate
from app.nowplaying.service import NowPlayingSources
from app.spotify.routes import accounts, pollers
from app.spotify.schemas import NowPlayingResponse

router = APIRouter(tags=["now-playing"])
sources = NowPlayingSources(accounts, pollers, feed_store, feeds)


@router.get("/api/now-playing/sources", response_model=SourcesResponse)
def get_sources(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return sources.info(session, user.id)


@router.put("/api/now-playing/source", response_model=SourcesResponse)
async def put_source(body: SourceUpdate, user: User = Depends(current_user), session: Session = Depends(get_session)):
    return sources.select(session, user.id, body.source)  # async: it notifies open streams


# Part of the feed's public contract (v1), but it needs the source choice, which lives here.
@router.get("/api/feed/v1/me", response_model=FeedMe, tags=["feed"])
def feed_me(
    user_id: int = Depends(feed_user),
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    return FeedMe(
        token_name=feed_store.token_name(bearer_token(authorization)) or "",
        feed_selected=sources.info(session, user_id).effective == "feed",
    )


async def _stream(user: User, session: Session):
    attached = sources.subscribe(session, user.id)
    session.close()  # the stream outlives the request; don't hold a DB session open
    if attached is None:
        raise HTTPException(status_code=409, detail="no now-playing source set up")
    _source, queue, unsubscribe = attached

    async def events():
        try:
            while True:
                state = await queue.get()
                if state == DISCONNECTED:
                    yield {"event": "spotify-disconnected", "data": "{}"}
                    return
                if state == RESUBSCRIBE:
                    return
                payload = NowPlayingResponse.model_validate(state, from_attributes=True)
                yield {"event": "now-playing", "data": payload.model_dump_json()}
        except asyncio.CancelledError:
            raise
        finally:
            unsubscribe()

    return EventSourceResponse(events())


@router.get("/api/now-playing/stream")
async def now_playing_stream(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return await _stream(user, session)


# Before 2026-10-15 the stream lived under /api/spotify; a car that hasn't reloaded
# since still asks there. Remove after a few weeks.
@router.get("/api/spotify/now-playing/stream", include_in_schema=False)
async def legacy_now_playing_stream(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return await _stream(user, session)
