from pydantic import BaseModel


class UserSchema(BaseModel):
    id: int
    email: str
    name: str
    role: str


class MeResponse(BaseModel):
    """200 even when signed out (user = null): loading the page is not a failed login,
    so it must not produce the 401s fail2ban counts (see ~/projects/AGENTS.md)."""

    user: UserSchema | None
    google_enabled: bool
    dev_login: bool
    lyrics_sources: list[str]  # providers this deployment has, e.g. ["netease", "lrclib"]


class DevLoginRequest(BaseModel):
    email: str


class PairStartResponse(BaseModel):
    code: str
    poll_secret: str
    approve_url: str
    qr_svg: str
    expires_in: int


class PairPollRequest(BaseModel):
    poll_secret: str


class PairPollResponse(BaseModel):
    status: str  # "pending" | "approved" | "expired"


class PairApproveRequest(BaseModel):
    code: str


class OkResponse(BaseModel):
    ok: bool
