from pydantic import BaseModel


class TableCount(BaseModel):
    name: str
    rows: int


class UserStats(BaseModel):
    id: int
    email: str
    role: str
    created_at: float
    last_seen_at: float | None  # newest session activity (refreshed at most daily)
    sessions: int
    spotify_app: bool
    spotify_connected: bool
    lyrics_source: str
    show_translation: bool
    screens_open: int  # SSE streams right now; >0 means their poller is running


class SourceStats(BaseModel):
    source: str
    tracks_matched: int  # rows pointing at a song
    tracks_not_found: int  # looked, nothing acceptable
    corrections: int  # manual rows pointing at a song
    marked_wrong: int  # manual rows saying "this source has the wrong song"


class TrackRow(BaseModel):
    title: str
    artist: str
    detail: str  # sources looked in / source picked
    by: str | None
    at: float


class StatsResponse(BaseModel):
    db_bytes: int
    tables: list[TableCount]
    users: list[UserStats]
    pollers_running: int
    screens_open: int
    sources: list[SourceStats]
    personal_source_pins: int
    counters_since: float
    counters: dict[str, int]  # since the process started: cached/searched, shown:<source>, error:<source>, picks
    not_found: list[TrackRow]  # newest first
    recent_picks: list[TrackRow]
