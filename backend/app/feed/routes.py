"""Two groups: the public contract (/api/feed/v1/*, authenticated by a feed token —
see docs/feed.md) and the signed-in user's management of their feed (session cookie).
Async throughout: the handlers touch the per-user runtime's asyncio objects, which must
stay on the event loop's thread."""

import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.auth.deps import current_user
from app.auth.models import User
from app.auth.schemas import OkResponse
from app.core.config import settings as app_settings
from app.core.rate_limit import MinInterval
from app.feed.adapter import HttpWebhookSender
from app.feed.deps import feed_user
from app.feed.linking import LINK_TTL_SECONDS, POLL_INTERVAL_SECONDS, LinkRegistry, display_code
from app.feed.schemas import (
    DeliveryResult,
    FeedPush,
    FeedPushAck,
    FeedSettingsResponse,
    FeedSettingsUpdate,
    FeedStatusResponse,
    FeedTokenCreate,
    FeedTokenCreated,
    FeedTokenInfo,
    FeedTokenList,
    LinkDecision,
    LinkInfo,
    LinkPoll,
    LinkPollResult,
    LinkStart,
    LinkStarted,
    PingEvent,
    RefreshRequest,
    WebhookSaved,
    WebhookSecret,
    WebhookUpdate,
)
from app.feed.service import FeedRegistry, RefreshRefused, TooManyReceivers, feed_status
from app.feed.store import FeedStore, TooManyTokens

router = APIRouter(prefix="/api/feed", tags=["feed"])
store = FeedStore()
sender = HttpWebhookSender()
feeds = FeedRegistry(store, sender)
links = LinkRegistry()

_push_limit = MinInterval(0.5)  # two pushes a second per user
_test_limit = MinInterval(10.0)
_link_start_limit = MinInterval(2.0)  # per client address
_link_poll_limit = MinInterval(POLL_INTERVAL_SECONDS - 0.5)  # per poll secret

KEEPALIVE_SECONDS = 15


# --- Public contract, v1 ------------------------------------------------------------


@router.post("/v1/now-playing", response_model=FeedPushAck)
async def push(body: FeedPush, user_id: int = Depends(feed_user)):
    if not _push_limit.allow(user_id):
        raise HTTPException(status_code=429, detail="at most two pushes a second")
    return feeds.feed(user_id).on_push(body)


@router.get("/v1/events")
async def events(user_id: int = Depends(feed_user)):
    feed = feeds.feed(user_id)
    try:
        queue = feed.attach_receiver()
    except TooManyReceivers:
        raise HTTPException(status_code=429, detail="too many open event streams for this account")

    async def stream():
        try:
            while True:
                event_type, body = await queue.get()
                yield {"event": event_type, "data": body}
        finally:
            feed.detach_receiver(queue)

    return EventSourceResponse(stream(), ping=KEEPALIVE_SECONDS)


def _client_address(request: Request) -> str:
    # Behind Cloudflare → Caddy: the visitor's address is in Cf-Connecting-Ip.
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "")


@router.post("/v1/link", response_model=LinkStarted)
async def link_start(body: LinkStart, request: Request):
    if not _link_start_limit.allow(_client_address(request)):
        raise HTTPException(status_code=429, detail="one link request every 2 seconds")
    code, poll_secret = links.start(body.client_name)
    return LinkStarted(
        code=display_code(code),
        verify_url=f"{app_settings.public_base_url}/link?code={code}",
        poll_secret=poll_secret,
        interval_s=POLL_INTERVAL_SECONDS,
        expires_in_s=LINK_TTL_SECONDS,
    )


@router.post("/v1/link/poll", response_model=LinkPollResult)
async def link_poll(body: LinkPoll):
    if not _link_poll_limit.allow(body.poll_secret):
        raise HTTPException(status_code=429, detail=f"poll at most every {POLL_INTERVAL_SECONDS} seconds")
    status, token = links.poll(body.poll_secret)
    return LinkPollResult(status=status, token=token)


# --- The signed-in user's feed ------------------------------------------------------


def _token_info(row) -> FeedTokenInfo:
    return FeedTokenInfo(id=row.id, name=row.name, prefix=row.prefix, created_at=row.created_at, last_used_at=row.last_used_at)


def _settings(user_id: int) -> FeedSettingsResponse:
    row = store.settings(user_id)
    webhook = store.webhook(user_id)
    return FeedSettingsResponse(
        skip_check_s=row.skip_check_s,
        paused_check_s=row.paused_check_s,
        monthly_budget=row.monthly_budget,
        hourly_cap=row.hourly_cap,
        webhook_url=webhook.url if webhook else "",
        webhook_paused=row.webhook_paused,
    )


@router.get("/status", response_model=FeedStatusResponse)
async def status(user: User = Depends(current_user)):
    return feed_status(feeds.feed(user.id), store)


@router.get("/tokens", response_model=FeedTokenList)
async def list_tokens(user: User = Depends(current_user)):
    return FeedTokenList(tokens=[_token_info(t) for t in store.tokens(user.id)])


@router.post("/tokens", response_model=FeedTokenCreated)
async def create_token(body: FeedTokenCreate, user: User = Depends(current_user)):
    try:
        token, row = store.create_token(user.id, body.name)
    except TooManyTokens:
        raise HTTPException(status_code=409, detail="at most 10 tokens; revoke one first")
    return FeedTokenCreated(token=token, info=_token_info(row))


@router.delete("/tokens/{token_id}", response_model=OkResponse)
async def revoke_token(token_id: int, user: User = Depends(current_user)):
    if not store.revoke_token(user.id, token_id):
        raise HTTPException(status_code=404, detail="no such token")
    if not store.has_tokens(user.id):
        feeds.disable(user.id)  # nothing can push any more: screens fall back to Spotify
    return OkResponse(ok=True)


@router.get("/settings", response_model=FeedSettingsResponse)
async def get_settings(user: User = Depends(current_user)):
    return _settings(user.id)


@router.put("/settings", response_model=FeedSettingsResponse)
async def put_settings(body: FeedSettingsUpdate, user: User = Depends(current_user)):
    store.update_settings(user.id, body)
    feeds.feed(user.id).settings_changed()
    return _settings(user.id)


@router.put("/webhook", response_model=WebhookSaved)
async def put_webhook(body: WebhookUpdate, user: User = Depends(current_user)):
    problem = await sender.check(body.url)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    secret = store.set_webhook(user.id, body.url)
    feeds.feed(user.id).settings_changed()
    return WebhookSaved(url=body.url.strip(), secret=secret)


@router.delete("/webhook", response_model=OkResponse)
async def delete_webhook(user: User = Depends(current_user)):
    store.clear_webhook(user.id)
    return OkResponse(ok=True)


@router.post("/webhook/secret", response_model=WebhookSecret)
async def rotate_secret(user: User = Depends(current_user)):
    if store.webhook(user.id) is None:
        raise HTTPException(status_code=409, detail="no webhook")
    return WebhookSecret(secret=store.rotate_webhook_secret(user.id))


@router.post("/webhook/test", response_model=DeliveryResult)
async def test_webhook(user: User = Depends(current_user)):
    webhook = store.webhook(user.id)
    if webhook is None:
        raise HTTPException(status_code=409, detail="no webhook")
    if not _test_limit.allow(user.id):
        raise HTTPException(status_code=429, detail="one test every 10 seconds")
    event = PingEvent(id=secrets.token_urlsafe(8), at=int(time.time() * 1000))
    return await sender.deliver(webhook.url, webhook.secret, event.model_dump_json().encode(), event.type)


@router.post("/refresh", response_model=OkResponse)
async def refresh(body: RefreshRequest, user: User = Depends(current_user)):
    try:
        feeds.feed(user.id).request_refresh(body.confirm_over_budget)
    except RefreshRefused as refused:
        raise HTTPException(status_code=409 if refused.reason == "monthly" else 429, detail=refused.reason)
    return OkResponse(ok=True)


@router.get("/link", response_model=LinkInfo)
async def link_info(code: str, user: User = Depends(current_user)):
    link = links.pending(code)
    if link is None:
        raise HTTPException(status_code=404, detail="code not found or expired")
    return LinkInfo(code=display_code(link.code), client_name=link.client_name)


@router.post("/link/approve", response_model=FeedTokenInfo)
async def link_approve(body: LinkDecision, user: User = Depends(current_user)):
    link = links.pending(body.code)
    if link is None:
        raise HTTPException(status_code=404, detail="code not found or expired")
    try:
        token, row = store.create_token(user.id, link.client_name)
    except TooManyTokens:
        raise HTTPException(status_code=409, detail="at most 10 tokens; revoke one first")
    links.approve(body.code, token)
    return _token_info(row)


@router.post("/link/deny", response_model=OkResponse)
async def link_deny(body: LinkDecision, user: User = Depends(current_user)):
    if not links.deny(body.code):
        raise HTTPException(status_code=404, detail="code not found or expired")
    return OkResponse(ok=True)
