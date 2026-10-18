import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from app.account.routes import router as account_router
from app.admin.routes import router as admin_router
from app.auth.deps import SessionCookieMiddleware
from app.auth.routes import router as auth_router
from app.auth.service import prune_dead_sessions
from app.core.db import engine, init_db
from app.core.openapi import with_stream_schemas
from app.feed.routes import feeds
from app.feed.routes import router as feed_router
from app.feed.schemas import FeedEvent, FetchEvent, PingEvent, StopEvent
from app.lyrics.routes import router as lyrics_router
from app.nowplaying.routes import router as nowplaying_router
from app.recognize.routes import router as recognize_router
from app.preferences.routes import router as preferences_router
from app.spotify.routes import pollers
from app.spotify.routes import router as spotify_router
from app.spotify.schemas import NowPlayingResponse

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as db:
        prune_dead_sessions(db)
    yield
    await pollers.stop_all()
    await feeds.stop_all()


app = FastAPI(title="lyric", lifespan=lifespan)
app.add_middleware(SessionCookieMiddleware)
app.include_router(auth_router)
app.include_router(spotify_router)
app.include_router(lyrics_router)
app.include_router(preferences_router)
app.include_router(admin_router)
app.include_router(account_router)
app.include_router(feed_router)
app.include_router(nowplaying_router)
app.include_router(recognize_router)
app.openapi = with_stream_schemas(app, [NowPlayingResponse, FeedEvent, FetchEvent, StopEvent, PingEvent])  # type: ignore[method-assign]


@app.get("/health")
def health():
    return {"status": "ok"}
