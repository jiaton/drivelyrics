from pydantic import BaseModel, Field


class RecognizerKeyStatus(BaseModel):
    configured: bool
    hint: str  # "…a1b2" when configured


class RecognizerKeyUpdate(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class RecognizeResponse(BaseModel):
    matched: bool
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    duration_ms: int | None = None
    track_id: str | None = None  # a Spotify id when known (shares lyrics fixes), else a title+artist id
    position_ms: int | None = None  # where the song was when the recording STARTED
    exact: bool = False  # position measured to ±0.5 s; False = estimated (±a few s)
