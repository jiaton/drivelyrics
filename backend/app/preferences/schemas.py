from typing import Literal

from pydantic import BaseModel

LyricsSource = Literal["auto", "netease", "lrclib"]


class PreferencesResponse(BaseModel):
    show_translation: bool
    show_album_art: bool
    keep_screen_awake: bool
    lyrics_source: LyricsSource


class PreferencesUpdate(BaseModel):
    """All fields optional — PATCH-style partial update. `None` means "leave as is",
    which is why these can't just reuse PreferencesResponse's non-optional fields."""

    show_translation: bool | None = None
    show_album_art: bool | None = None
    keep_screen_awake: bool | None = None
    lyrics_source: LyricsSource | None = None
