from sqlmodel import Field, SQLModel


class UserPreferences(SQLModel, table=True):
    """Display preferences (settings modal), one row per user, created on first read."""

    user_id: int = Field(primary_key=True, foreign_key="users.id")
    show_translation: bool = Field(default=False)
    show_album_art: bool = Field(default=True)
    keep_screen_awake: bool = Field(default=True)
    # "auto" | "netease" | "lrclib" — which lyrics provider to try first. See
    # lyrics/order.source_order for what "auto" means.
    # server_default too: migration step 1 inserts with raw SQL into tables built from
    # these current models, so every column added later needs a DB-side default.
    lyrics_source: str = Field(default="auto", sa_column_kwargs={"server_default": "auto"})
    # Jyutping under each line of Cantonese songs (lyrics/jyutping.py).
    show_jyutping: bool = Field(default=False, sa_column_kwargs={"server_default": "0"})
    # "spotify" | "feed": where now-playing comes from (nowplaying/service.py; set through
    # PUT /api/now-playing/source, which also reconnects open screens).
    now_playing_source: str = Field(default="spotify", sa_column_kwargs={"server_default": "spotify"})
    # Lyrics timing nudge for every source, ms: positive = lines change earlier.
    sync_offset_ms: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
