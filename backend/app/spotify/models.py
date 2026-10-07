from sqlmodel import Field, SQLModel


class SpotifyApp(SQLModel, table=True):
    """Each user brings their own Spotify Developer app (development-mode apps only
    admit users the app owner allow-lists by hand, so one shared app can't scale).
    The secret is Fernet-encrypted (core/crypto.py)."""

    user_id: int = Field(primary_key=True, foreign_key="users.id")
    client_id: str
    client_secret_enc: str


class SpotifyToken(SQLModel, table=True):
    user_id: int = Field(primary_key=True, foreign_key="users.id")
    access_token_enc: str
    refresh_token_enc: str
    expires_at: float  # unix timestamp
