from pydantic import BaseModel


class LyricLineSchema(BaseModel):
    t: int
    text: str


class LyricsResponse(BaseModel):
    lines: list[LyricLineSchema]
    translation_lines: list[LyricLineSchema]
    source: str  # "netease" | "lrclib" | "" when nothing matched
    song_id: str
    manual: bool  # someone picked this match by hand


class CandidateSchema(BaseModel):
    source: str
    song_id: str
    # The source of the lyrics the reader was shown, when they say those were the wrong
    # song. Omitted = they just prefer the picked source for this track (personal).
    wrong_source: str | None = None
    name: str
    artists: list[str]
    album: str | None
    duration_ms: int | None
    score: float
    selected: bool


class CandidatesResponse(BaseModel):
    candidates: list[CandidateSchema]


class ChoiceRequest(BaseModel):
    track_id: str
    title: str
    artist: str
    duration_ms: int | None = None
    source: str
    song_id: str
    # The source of the lyrics the reader was shown, when they say those were the wrong
    # song. Omitted = they just prefer the picked source for this track (personal).
    wrong_source: str | None = None
