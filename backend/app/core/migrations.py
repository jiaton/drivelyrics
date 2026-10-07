"""Schema versions, tracked in SQLite's own `PRAGMA user_version` — no Alembic: one
SQLite file, one process, a handful of tables. Each step runs once, in order, inside
one transaction (a real one on the app engine, DDL included — see core/db.py; the
data checks still run before anything is dropped). Add a step by appending to STEPS; never edit a shipped one.

The only cross-domain module besides main.py: a migration moves data between domains'
tables, so it imports their models."""

import time
from collections.abc import Callable

from sqlalchemy import Connection, Engine, text
from sqlmodel import SQLModel

from app.auth.models import AuthSession, User  # noqa: F401  (registers tables)
from app.core.config import settings
from app.core.crypto import encrypt
from app.lyrics.models import LyricsText, TrackMatch  # noqa: F401
from app.preferences.models import UserPreferences  # noqa: F401
from app.spotify.models import SpotifyApp, SpotifyToken  # noqa: F401


def _tables(conn: Connection) -> set[str]:
    return {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}


def _v1_multi_user(conn: Connection) -> None:
    """Single-user → multi-user. The single-user DB had singleton rows (id=1) for the
    Spotify token and preferences, and a lyrics cache keyed by title+artist. The token
    and preferences move to an owner account (OWNER_EMAIL); the old lyrics cache is
    dropped and rebuilt per Spotify track id by the new matcher."""
    old = _tables(conn)
    legacy_token = conn.execute(text("SELECT access_token, refresh_token, expires_at FROM spotifytoken WHERE id = 1")).first() if "spotifytoken" in old else None
    legacy_prefs = conn.execute(text("SELECT show_translation, show_album_art, keep_screen_awake FROM userpreferences WHERE id = 1")).first() if "userpreferences" in old else None
    # Checked before anything is dropped, not relied on a rollback for.
    if (legacy_token or legacy_prefs) and not settings.owner_email:
        raise RuntimeError("OWNER_EMAIL must be set to migrate the existing Spotify link to an account")
    if legacy_token and not (settings.spotify_client_id and settings.spotify_client_secret):
        raise RuntimeError("SPOTIFY_CLIENT_ID/SECRET must be set to migrate the existing Spotify link")
    for table in ("spotifytoken", "userpreferences", "lyricscache"):
        if table in old:
            conn.execute(text(f"DROP TABLE {table}"))  # fixed names, not input

    SQLModel.metadata.create_all(conn)

    if legacy_token is None and legacy_prefs is None:
        return
    now = time.time()
    user_id = conn.execute(
        text("INSERT INTO users (email, name, picture_url, role, created_at) VALUES (:email, '', '', 'admin', :now) RETURNING id"),
        {"email": settings.owner_email.strip().lower(), "now": now},
    ).scalar_one()
    if legacy_token is not None:
        conn.execute(
            text("INSERT INTO spotifyapp (user_id, client_id, client_secret_enc) VALUES (:u, :cid, :sec)"),
            {"u": user_id, "cid": settings.spotify_client_id, "sec": encrypt(settings.spotify_client_secret)},
        )
        conn.execute(
            text("INSERT INTO spotifytoken (user_id, access_token_enc, refresh_token_enc, expires_at) VALUES (:u, :a, :r, :e)"),
            {"u": user_id, "a": encrypt(legacy_token[0]), "r": encrypt(legacy_token[1]), "e": legacy_token[2]},
        )
    if legacy_prefs is not None:
        conn.execute(
            text("INSERT INTO userpreferences (user_id, show_translation, show_album_art, keep_screen_awake) VALUES (:u, :t, :a, :k)"),
            {"u": user_id, "t": legacy_prefs[0], "a": legacy_prefs[1], "k": legacy_prefs[2]},
        )


def _columns(conn: Connection, table: str) -> dict[str, int]:
    """Column name → position in the primary key (0 = not part of it)."""
    return {row[1]: row[5] for row in conn.execute(text(f"PRAGMA table_info({table})"))}


def _v2_lyrics_source(conn: Connection) -> None:
    """Per-user lyrics source preference, and one TrackMatch row per (track, source)
    instead of per track. Step 1 creates tables from the *current* models, so on a
    database created fresh after this step shipped both changes already exist —
    hence the checks."""
    if "lyrics_source" not in _columns(conn, "userpreferences"):
        conn.execute(text("ALTER TABLE userpreferences ADD COLUMN lyrics_source VARCHAR NOT NULL DEFAULT 'auto'"))
    if _columns(conn, "trackmatch").get("source") == 0:  # old shape: track id alone is the key
        conn.execute(text("ALTER TABLE trackmatch RENAME TO trackmatch_v1"))
        SQLModel.metadata.tables["trackmatch"].create(conn)
        # Rows that found nothing carry no source; they're re-searched per source.
        conn.execute(text(
            "INSERT INTO trackmatch (spotify_track_id, source, title, artist, source_song_id, match_version, manual, chosen_by, updated_at) "
            "SELECT spotify_track_id, source, title, artist, source_song_id, match_version, manual, chosen_by, updated_at "
            "FROM trackmatch_v1 WHERE source != ''"
        ))
        conn.execute(text("DROP TABLE trackmatch_v1"))


STEPS: list[Callable[[Connection], None]] = [_v1_multi_user, _v2_lyrics_source]


def migrate(engine: Engine) -> None:
    with engine.begin() as conn:
        version = conn.execute(text("PRAGMA user_version")).scalar_one()
        for number, step in enumerate(STEPS[version:], start=version + 1):
            step(conn)
            conn.execute(text(f"PRAGMA user_version = {int(number)}"))
        # Brand-new tables added later without a data step still appear here.
        SQLModel.metadata.create_all(conn)
