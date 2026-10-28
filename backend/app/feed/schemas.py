"""Two kinds of models. The public contract (v1): what a user's side pushes and the
events it receives — documented in docs/feed.md, exported as JSON Schema to
docs/feed/v1/ (scripts/export_contract.py), and only ever extended, never changed,
within v1. And the signed-in user's management of their feed (tokens, settings,
status), which only this app's frontend uses."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

# --- Public contract, v1 ------------------------------------------------------------

FetchReason = Literal["opened", "track_ending", "skip_check", "paused_check", "refresh", "retry"]
_MAX_MS = 86_400_000


class FeedPush(BaseModel):
    """What is playing right now, pushed by the user's side (POST /api/feed/v1/now-playing)."""

    # Unknown fields are ignored, so a newer client can talk to this server.
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    playing: bool
    title: str | None = Field(default=None, max_length=300, description="Required while playing.")
    artist: str | None = Field(default=None, max_length=300)
    album: str | None = Field(default=None, max_length=300)
    duration_ms: int | None = Field(default=None, ge=0, le=_MAX_MS, description="Strongly recommended: lets DriveLyrics ask for the next track right after this one ends.")
    position_ms: int | None = Field(default=None, ge=0, le=_MAX_MS, description="Playback position; omitted on a new track = 0.")
    source: str | None = Field(default=None, max_length=40, description='Shown to the user only, e.g. "Spotify", "Bluetooth".')
    measured_at: int | None = Field(default=None, ge=0, description="Unix ms when position_ms was read; ignored when more than 5 minutes off the server clock.")
    fetch_id: str | None = Field(default=None, max_length=64, description="The id of the fetch event this answers, if any.")
    limited: Literal["hourly", "monthly"] | None = Field(
        default=None,
        description="Set when this answer is what the sender already knew, without reading the player, because the sender's own read limit is reached. Shown on the user's screens.",
    )

    @field_validator("title", "artist", "album", "source")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def _title_while_playing(self) -> "FeedPush":
        if self.playing and not self.title:
            raise ValueError("title is required while playing")
        return self


class FeedPushAck(BaseModel):
    """For clients that don't listen to events: when to push next, if at all."""

    watching: bool = Field(description="A DriveLyrics screen of this user is open.")
    next_fetch_in_ms: int | None = Field(description="When DriveLyrics would next ask for an update; null = no update needed.")


class FetchEvent(BaseModel):
    """Read the player once and push the result."""

    type: Literal["fetch"] = "fetch"
    id: str
    reason: FetchReason = Field(description="Informational; treat every fetch the same. New reasons may be added within v1.")
    at: int = Field(description="Unix ms.")


class StopEvent(BaseModel):
    """No screen is open any more: no fetches until the next "opened"."""

    type: Literal["stop"] = "stop"
    at: int


class PingEvent(BaseModel):
    """Sent by the "Test" button in settings; needs no answer."""

    type: Literal["ping"] = "ping"
    id: str
    at: int


class FeedEvent(RootModel[Annotated[FetchEvent | StopEvent | PingEvent, Field(discriminator="type")]]):
    """One event, on the event stream (GET /api/feed/v1/events) or as a webhook body."""


class FeedMe(BaseModel):
    """What a token is (GET /api/feed/v1/me): for a receiver to check its token and
    whether the user's screens will show what it pushes."""

    token_name: str
    feed_selected: bool = Field(description="The user's screens show the feed (Settings → Now playing from); false = pushes are kept but not shown.")


class LinkStart(BaseModel):
    """Ask to be linked to someone's account without a token (POST /api/feed/v1/link)."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    client_name: str = Field(min_length=1, max_length=40, description='Becomes the token\'s name, e.g. "Home Assistant".')


class LinkStarted(BaseModel):
    code: str = Field(description='Shown to the user, e.g. "ABCD-EFGH".')
    verify_url: str = Field(description="Where the user approves, with the code filled in.")
    poll_secret: str = Field(description="Keep it to yourself; poll with it.")
    interval_s: int = Field(description="Poll no more often than this.")
    expires_in_s: int


class LinkPoll(BaseModel):
    poll_secret: str = Field(max_length=100)


class LinkPollResult(BaseModel):
    status: Literal["pending", "approved", "denied", "expired"]
    token: str | None = Field(default=None, description="With approved: the new feed token, handed out this once.")


# --- The signed-in user's management of their feed ----------------------------------


class FeedTokenInfo(BaseModel):
    id: int
    name: str
    prefix: str
    created_at: float
    last_used_at: float | None


class FeedTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class FeedTokenCreated(BaseModel):
    token: str  # shown this once
    info: FeedTokenInfo


class FeedTokenList(BaseModel):
    tokens: list[FeedTokenInfo]


class LinkInfo(BaseModel):
    """A pending link, as the approval page shows it."""

    code: str
    client_name: str


class LinkDecision(BaseModel):
    code: str = Field(max_length=20)


class FeedSettingsResponse(BaseModel):
    skip_check_s: Literal[0, 30, 60]
    paused_check_s: Literal[0, 60, 120]
    monthly_budget: int
    hourly_cap: int
    webhook_url: str  # "" = none
    webhook_paused: bool


class FeedSettingsUpdate(BaseModel):
    skip_check_s: Literal[0, 30, 60] | None = None
    paused_check_s: Literal[0, 60, 120] | None = None
    monthly_budget: int | None = Field(default=None, ge=0, le=100_000)
    hourly_cap: int | None = Field(default=None, ge=1, le=600)


class WebhookUpdate(BaseModel):
    url: str = Field(min_length=8, max_length=500)


class WebhookSecret(BaseModel):
    secret: str  # shown this once


class WebhookSaved(BaseModel):
    url: str
    secret: str | None  # a new signing secret, shown this once; None = the existing one stays


class DeliveryResult(BaseModel):
    ok: bool
    detail: str


class RefreshRequest(BaseModel):
    confirm_over_budget: bool = False


class EventLog(BaseModel):
    at: float
    reason: str
    delivered: bool


class PushLog(BaseModel):
    at: float
    playing: bool
    title: str | None
    artist: str | None
    source: str | None


class FeedStatusResponse(BaseModel):
    enabled: bool  # has at least one token
    watching: bool
    receivers: int  # open event-stream connections
    webhook: Literal["off", "ok", "failing", "paused", "unused"]
    webhook_detail: str
    last_event: EventLog | None
    last_push: PushLog | None
    not_responding: bool  # fetches went unanswered
    blocked: Literal["", "hourly", "monthly"]
    month: str
    month_fetches: int
    monthly_budget: int
    hour_fetches: int  # in the last 60 minutes
    hourly_cap: int  # per hour on average (token bucket)
    hour_burst: int  # at most this many back to back
    hour_left: int  # may go out right now
    receiver_limited: Literal["", "hourly", "monthly"]  # the user's side's own limit, from its last push
    stopped: str  # why the scheduler last stopped ("" while running or never ran)
