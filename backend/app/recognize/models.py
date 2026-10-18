from sqlmodel import Field, SQLModel


class RecognizerKey(SQLModel, table=True):
    """A user's own music-recognition API key (AudD), Fernet-encrypted: each user pays
    for their own recognitions, like each brings their own Spotify app."""

    user_id: int = Field(primary_key=True, foreign_key="users.id")
    provider: str = Field(default="audd")
    token_enc: str
    hint: str  # last 4 characters, to show which key is saved
    created_at: float
