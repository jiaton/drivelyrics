from urllib.parse import quote, urlsplit

import segno
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlmodel import Session

from app.auth.adapter import GoogleOAuthClient
from app.auth.deps import current_user, optional_user, session_cookie_header
from app.auth.models import User
from app.auth.schemas import (
    DevLoginRequest,
    MeResponse,
    OkResponse,
    PairApproveRequest,
    PairPollRequest,
    PairPollResponse,
    PairStartResponse,
    UserSchema,
)
from app.auth.service import (
    COOKIE_NAME,
    PAIR_TTL_SECONDS,
    SessionError,
    create_session,
    delete_session,
    pairings,
    user_for_dev_login,
    user_for_google,
)
from app.core.config import settings
from app.core.db import get_session
from app.core.one_time_states import OneTimeStates

router = APIRouter(prefix="/api/auth", tags=["auth"])
google = GoogleOAuthClient()
google_states: OneTimeStates[str] = OneTimeStates()  # payload: where to go after sign-in
# Session handoff from an old hostname (payload: user id). Short-lived: it is used by an
# immediate redirect, never shown to a person.
handoffs: OneTimeStates[int] = OneTimeStates(ttl_seconds=120)

GOOGLE_REDIRECT_URI = f"{settings.public_base_url}/api/auth/google/callback"


def _safe_next(next_path: str | None) -> str:
    # Same-origin paths only: "/pair?code=X" yes, "//evil.com" or "https://…" no.
    if next_path and next_path.startswith("/") and not next_path.startswith("//") and "\\" not in next_path:
        return next_path
    return "/"


def _signed_in(response, token: str):
    response.headers.append("set-cookie", session_cookie_header(token))
    return response


@router.get("/me", response_model=MeResponse)
def me(user: User | None = Depends(optional_user)):
    return MeResponse(
        user=UserSchema.model_validate(user, from_attributes=True) if user else None,
        google_enabled=bool(settings.google_client_id),
        dev_login=settings.dev_login,
        lyrics_sources=(["netease"] if settings.netease_api_base_url else []) + ["lrclib"],
    )


@router.get("/google/start")
def google_start(next: str | None = Query(None)):
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    state = google_states.issue(_safe_next(next))
    return RedirectResponse(google.build_authorize_url(state, GOOGLE_REDIRECT_URI))


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_session),
):
    next_path = google_states.consume(state) if state else None
    if error or not code or next_path is None:
        return RedirectResponse("/?signin=failed")
    try:
        identity = await google.identify(code, GOOGLE_REDIRECT_URI)
        user = user_for_google(db, identity)
    except SessionError:
        return RedirectResponse("/?signin=failed")
    token = create_session(db, user.id, "google", request.headers.get("user-agent", ""))
    return _signed_in(RedirectResponse(next_path, status_code=303), token)


@router.post("/dev-login", response_model=UserSchema)
def dev_login(body: DevLoginRequest, request: Request, db: Session = Depends(get_session)):
    if not settings.dev_login:
        raise HTTPException(status_code=404)
    user = user_for_dev_login(db, body.email)
    token = create_session(db, user.id, "dev", request.headers.get("user-agent", ""))
    return _signed_in(JSONResponse(UserSchema.model_validate(user, from_attributes=True).model_dump()), token)


@router.post("/logout", response_model=OkResponse)
def logout(request: Request, db: Session = Depends(get_session)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        delete_session(db, token)
    response = JSONResponse(OkResponse(ok=True).model_dump())
    response.headers.append("set-cookie", session_cookie_header("", max_age=0))
    return response


@router.get("/handoff")
def handoff(request: Request, user: User | None = Depends(optional_user)):
    """Reached on a previous hostname (lyric.tjia.dev, lyrics.tjia.dev — Caddy sends
    every request there). Cookies are per host, so without this every browser, the car
    included, would have to sign in again after the move to PUBLIC_BASE_URL. If this
    browser has a session here, carry it over with a single-use token."""
    public = settings.public_base_url
    if user is None or request.url.hostname == urlsplit(public).hostname:
        return RedirectResponse(f"{public}/", status_code=302)
    return RedirectResponse(f"{public}/api/auth/handoff/complete?token={quote(handoffs.issue(user.id))}", status_code=302)


@router.get("/handoff/complete")
def handoff_complete(request: Request, token: str = Query(""), db: Session = Depends(get_session)):
    user_id = handoffs.consume(token) if token else None
    if user_id is None:
        return RedirectResponse("/", status_code=302)
    session_token = create_session(db, user_id, "handoff", request.headers.get("user-agent", ""))
    return _signed_in(RedirectResponse("/", status_code=302), session_token)


@router.post("/pair/start", response_model=PairStartResponse)
def pair_start(request: Request):
    code, poll_secret = pairings.start(request.headers.get("user-agent", ""))
    approve_url = f"{settings.public_base_url}/pair?code={quote(code)}"
    qr = segno.make(approve_url, error="m")
    return PairStartResponse(
        code=code,
        poll_secret=poll_secret,
        approve_url=approve_url,
        qr_svg=qr.svg_inline(scale=1, border=2, omitsize=True, dark="#000", light="#fff"),
        expires_in=PAIR_TTL_SECONDS,
    )


@router.post("/pair/poll", response_model=PairPollResponse)
def pair_poll(body: PairPollRequest, db: Session = Depends(get_session)):
    status, user_id, user_agent = pairings.poll(body.poll_secret)
    if status != "approved" or user_id is None:
        return PairPollResponse(status=status)
    token = create_session(db, user_id, "pairing", user_agent)
    return _signed_in(JSONResponse(PairPollResponse(status="approved").model_dump()), token)


@router.post("/pair/approve", response_model=OkResponse)
def pair_approve(body: PairApproveRequest, user: User = Depends(current_user)):
    if not pairings.approve(body.code, user.id):
        raise HTTPException(status_code=404, detail="code not found or expired")
    return OkResponse(ok=True)
