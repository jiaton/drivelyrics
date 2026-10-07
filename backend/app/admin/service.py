"""Read-only numbers for the owner's stats page. Like core/migrations.py this reads
across domains' tables on purpose: it's a view over the whole app, not a domain."""

import os

from sqlalchemy import func, text
from sqlmodel import Session, select

from app.admin.schemas import SourceStats, StatsResponse, TableCount, TrackRow, UserStats
from app.auth.models import AuthSession, User
from app.core.config import settings
from app.lyrics.models import TrackMatch, UserTrackSource
from app.preferences.models import UserPreferences
from app.spotify.models import SpotifyApp, SpotifyToken

_TABLES = ["users", "authsession", "spotifyapp", "spotifytoken", "userpreferences", "trackmatch", "lyricstext", "usertracksource"]
_LIST_LIMIT = 50


def _db_bytes() -> int:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        try:
            total += os.path.getsize(settings.database_path + suffix)
        except OSError:
            pass
    return total


def collect(db: Session, pollers: list[tuple[int, int]], counters: dict[str, int], counters_since: float) -> StatsResponse:
    screens = dict(pollers)
    emails = {u.id: u.email for u in db.exec(select(User))}

    last_seen = dict(db.exec(select(AuthSession.user_id, func.max(AuthSession.last_seen_at)).group_by(AuthSession.user_id)).all())
    session_counts = dict(db.exec(select(AuthSession.user_id, func.count()).group_by(AuthSession.user_id)).all())
    apps = set(db.exec(select(SpotifyApp.user_id)).all())
    tokens = set(db.exec(select(SpotifyToken.user_id)).all())
    prefs = {p.user_id: p for p in db.exec(select(UserPreferences))}
    users = [
        UserStats(
            id=u.id,
            email=u.email,
            role=u.role,
            created_at=u.created_at,
            last_seen_at=last_seen.get(u.id),
            sessions=session_counts.get(u.id, 0),
            spotify_app=u.id in apps,
            spotify_connected=u.id in tokens,
            lyrics_source=prefs[u.id].lyrics_source if u.id in prefs else "auto",
            show_translation=prefs[u.id].show_translation if u.id in prefs else False,
            screens_open=screens.get(u.id, 0),
        )
        for u in db.exec(select(User).order_by(User.created_at))
    ]

    sources = []
    for source in db.exec(select(TrackMatch.source).distinct()).all():
        rows = db.exec(select(TrackMatch).where(TrackMatch.source == source)).all()
        sources.append(
            SourceStats(
                source=source,
                tracks_matched=sum(1 for r in rows if r.source_song_id),
                tracks_not_found=sum(1 for r in rows if not r.source_song_id and not r.manual),
                corrections=sum(1 for r in rows if r.manual and r.source_song_id),
                marked_wrong=sum(1 for r in rows if r.manual and not r.source_song_id),
            )
        )

    # Tracks where no source that was looked at has a song: what readers saw as
    # "No synced lyrics found" (or would, once they reach those sources).
    not_found = [
        TrackRow(title=row[0], artist=row[1], detail=row[2], by=None, at=row[3])
        for row in db.execute(text(
            "SELECT max(title), max(artist), group_concat(source, ', '), max(updated_at) FROM trackmatch "
            "GROUP BY spotify_track_id HAVING max(source_song_id) = '' ORDER BY max(updated_at) DESC LIMIT :n"
        ).bindparams(n=_LIST_LIMIT)).all()
    ]
    picks = [
        TrackRow(
            title=r.title,
            artist=r.artist,
            detail=f"{r.source}: {'marked wrong' if not r.source_song_id else r.source_song_id}",
            by=emails.get(r.chosen_by) if r.chosen_by else None,
            at=r.updated_at,
        )
        for r in db.exec(select(TrackMatch).where(TrackMatch.manual == True).order_by(TrackMatch.updated_at.desc()).limit(_LIST_LIMIT))  # noqa: E712
    ]

    return StatsResponse(
        db_bytes=_db_bytes(),
        tables=[TableCount(name=t, rows=db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one()) for t in _TABLES],  # fixed names
        users=users,
        pollers_running=len(pollers),
        screens_open=sum(screens.values()),
        sources=sources,
        personal_source_pins=db.exec(select(func.count()).select_from(UserTrackSource)).one(),
        counters_since=counters_since,
        counters=counters,
        not_found=not_found,
        recent_picks=picks,
    )
