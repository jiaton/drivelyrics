from sqlmodel import Field, SQLModel


class UserPreferences(SQLModel, table=True):
    """Display preferences (settings modal), one row per user, created on first read."""

    user_id: int = Field(primary_key=True, foreign_key="users.id")
    show_translation: bool = Field(default=False)
    show_album_art: bool = Field(default=True)
    keep_screen_awake: bool = Field(default=True)
    # "auto" | "netease" | "lrclib" — which lyrics provider to try first. See
    # lyrics/service.source_order for what "auto" means.
    # server_default too: migration step 1 inserts with raw SQL into tables built from
    # these current models, so every column added later needs a DB-side default.
    lyrics_source: str = Field(default="auto", sa_column_kwargs={"server_default": "auto"})
