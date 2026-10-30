from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """One account per email, however it signs in: Google, GitHub or a code sent to the
    email. A row can exist before its first login (the owner, created by the migration
    from OWNER_EMAIL); google_sub / github_id are filled on that provider's first login."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    google_sub: str | None = Field(default=None, unique=True, index=True)
    github_id: str | None = Field(default=None, unique=True, index=True)
    name: str = Field(default="")
    picture_url: str = Field(default="")  # unused, always "": we don't keep Google's profile picture
    role: str = Field(default="user")  # "user" | "admin"
    created_at: float


class AuthSession(SQLModel, table=True):
    """Server-side session. The cookie holds a random token; only its SHA-256 is stored,
    so a leaked DB file doesn't hand out logins. No expiry: a session lasts until the
    user logs out (see auth/service.py for how the cookie itself is kept alive)."""

    token_hash: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: float
    last_seen_at: float
    via: str  # "google" | "github" | "email" | "pairing" | "handoff" | "dev"
    user_agent: str = Field(default="")
