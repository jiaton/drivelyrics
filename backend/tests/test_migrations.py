import sqlite3

import pytest
from sqlalchemy import create_engine, text

from app.core import migrations
from app.core.crypto import decrypt

V0_SCHEMA = """
CREATE TABLE spotifytoken (id INTEGER PRIMARY KEY, access_token VARCHAR NOT NULL, refresh_token VARCHAR NOT NULL, expires_at FLOAT NOT NULL);
CREATE TABLE userpreferences (id INTEGER PRIMARY KEY, show_translation BOOLEAN NOT NULL, show_album_art BOOLEAN NOT NULL, keep_screen_awake BOOLEAN NOT NULL);
CREATE TABLE lyricscache (cache_key VARCHAR PRIMARY KEY, title VARCHAR, artist VARCHAR, lrc_text VARCHAR, source VARCHAR, fetched_at FLOAT, tlyric_text TEXT NOT NULL DEFAULT '', source_song_id TEXT NOT NULL DEFAULT '', match_version INTEGER NOT NULL DEFAULT 0);
INSERT INTO spotifytoken VALUES (1, 'old-access', 'old-refresh', 1234.5);
INSERT INTO userpreferences VALUES (1, 1, 0, 1);
INSERT INTO lyricscache VALUES ('a::b::1', 'a', 'b', '[00:01.00]x', 'netease', 0, '', '', 2);
"""


def _v0_db(tmp_path):
    path = tmp_path / "v0.db"
    conn = sqlite3.connect(path)
    conn.executescript(V0_SCHEMA)
    conn.close()
    return create_engine(f"sqlite:///{path}")


def test_single_user_data_moves_to_the_owner(tmp_path):
    engine = _v0_db(tmp_path)

    migrations.migrate(engine)

    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA user_version")).scalar_one() == len(migrations.STEPS)
        user = conn.execute(text("SELECT id, email, role FROM users")).one()
        assert user.email == "owner@example.com" and user.role == "admin"
        app = conn.execute(text("SELECT user_id, client_id, client_secret_enc FROM spotifyapp")).one()
        assert (app.user_id, app.client_id) == (user.id, "legacy-client-id")
        assert decrypt(app.client_secret_enc) == "legacy-client-secret"
        token = conn.execute(text("SELECT * FROM spotifytoken")).one()
        assert decrypt(token.access_token_enc) == "old-access"
        assert decrypt(token.refresh_token_enc) == "old-refresh"
        assert token.expires_at == 1234.5
        prefs = conn.execute(text("SELECT * FROM userpreferences")).one()
        assert (prefs.user_id, prefs.show_translation, prefs.show_album_art, prefs.keep_screen_awake) == (user.id, 1, 0, 1)
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        assert "lyricscache" not in tables and "trackmatch" in tables


def test_migrate_is_idempotent(tmp_path):
    engine = _v0_db(tmp_path)
    migrations.migrate(engine)
    migrations.migrate(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1


def test_fresh_database_gets_the_current_schema(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    migrations.migrate(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 0


def test_refuses_to_drop_a_link_it_cannot_assign(tmp_path, monkeypatch):
    engine = _v0_db(tmp_path)
    monkeypatch.setattr(migrations.settings, "owner_email", "")
    with pytest.raises(RuntimeError):
        migrations.migrate(engine)
    with engine.connect() as conn:  # rolled back: the old token is still there
        assert conn.execute(text("SELECT access_token FROM spotifytoken")).scalar_one() == "old-access"


V1_TRACKMATCH = """
CREATE TABLE trackmatch (spotify_track_id VARCHAR PRIMARY KEY, title VARCHAR NOT NULL, artist VARCHAR NOT NULL, source VARCHAR NOT NULL, source_song_id VARCHAR NOT NULL, match_version INTEGER NOT NULL, manual BOOLEAN NOT NULL, chosen_by INTEGER, updated_at FLOAT NOT NULL);
INSERT INTO trackmatch VALUES ('t-picked', 'A', 'B', 'netease', '42', 3, 1, 1, 0);
INSERT INTO trackmatch VALUES ('t-none', 'C', 'D', '', '', 3, 0, NULL, 0);
CREATE TABLE userpreferences (user_id INTEGER PRIMARY KEY, show_translation BOOLEAN NOT NULL, show_album_art BOOLEAN NOT NULL, keep_screen_awake BOOLEAN NOT NULL);
INSERT INTO userpreferences VALUES (1, 1, 1, 1);
PRAGMA user_version = 1;
"""


def test_v2_keys_matches_per_source_and_keeps_manual_picks(tmp_path):
    path = tmp_path / "v1.db"
    conn = sqlite3.connect(path)
    conn.executescript(V1_TRACKMATCH)
    conn.close()
    engine = create_engine(f"sqlite:///{path}")

    migrations.migrate(engine)

    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA user_version")).scalar_one() == len(migrations.STEPS)
        rows = conn.execute(text("SELECT spotify_track_id, source, source_song_id, manual FROM trackmatch")).all()
        assert [tuple(r) for r in rows] == [("t-picked", "netease", "42", 1)]  # "found nothing" rows re-search
        assert conn.execute(text("SELECT lyrics_source FROM userpreferences")).scalar_one() == "auto"


def test_v3_forgets_stored_profile_pictures(tmp_path):
    path = tmp_path / "v2.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR NOT NULL, google_sub VARCHAR, name VARCHAR NOT NULL, picture_url VARCHAR NOT NULL, role VARCHAR NOT NULL, created_at FLOAT NOT NULL);
INSERT INTO users VALUES (1, 'a@example.com', 'sub', 'A', 'https://lh3.googleusercontent.com/x', 'admin', 0);
PRAGMA user_version = 2;
""")
    conn.close()
    engine = create_engine(f"sqlite:///{path}")
    migrations.migrate(engine)
    with engine.connect() as c:
        assert c.execute(text("SELECT picture_url FROM users")).scalar_one() == ""
