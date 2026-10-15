from sqlmodel import Field, SQLModel


class FeedToken(SQLModel, table=True):
    """A push token for the now-playing feed: write-only (it can set what this user is
    playing and receive "fetch" events, nothing else). Several per user, each named
    after where it lives ("Home Assistant"), so one can be replaced without downtime.
    Only a SHA-256 of the token is stored; the token is shown once, at creation."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    name: str
    prefix: str  # the token's first characters, to tell tokens apart in the UI
    token_hash: str = Field(unique=True, index=True)
    created_at: float
    last_used_at: float | None = Field(default=None)


class FeedSettings(SQLModel, table=True):
    """How often DriveLyrics asks the user's side to read their player (see
    feed/schedule.py), what that may cost them, and the optional webhook."""

    user_id: int = Field(primary_key=True, foreign_key="users.id")
    skip_check_s: int = Field(default=0)  # 0 = off; else check for a skipped track this often
    paused_check_s: int = Field(default=0)  # 0 = off; else check a paused player this often
    monthly_budget: int = Field(default=1000)  # fetch events per calendar month (UTC)
    hourly_cap: int = Field(default=60)  # fetch events per rolling hour: a guard against bugs
    webhook_url_enc: str = Field(default="")  # Fernet; "" = no webhook
    webhook_secret_enc: str = Field(default="")  # Fernet; HMAC key for X-DriveLyrics-Signature
    webhook_paused: bool = Field(default=False)  # set after repeated failures; saving the URL clears it


class FeedUsage(SQLModel, table=True):
    """Fetch events delivered per user per month, for the budget. Kept in the DB so a
    restart doesn't reset what the user has spent."""

    user_id: int = Field(primary_key=True, foreign_key="users.id")
    month: str = Field(primary_key=True)  # "2026-10", UTC
    fetches: int = Field(default=0)
