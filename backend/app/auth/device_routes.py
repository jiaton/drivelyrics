"""Devices: signing a screen in by pairing, and the browsers signed in to an account."""

from urllib.parse import quote

import segno
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.auth.deps import client_ip, current_user, session_cookie_header, signed_in
from app.auth.models import User
from app.auth.pairing import PAIR_TTL_SECONDS, pairings
from app.auth.schemas import (
    OkResponse,
    PairApproveRequest,
    PairInfoResponse,
    PairPollRequest,
    PairPollResponse,
    PairStartResponse,
    SessionInfo,
    SessionList,
)
from app.auth.service import (
    COOKIE_NAME,
    create_session,
    delete_all_sessions,
    delete_user_session,
    describe_device,
    list_sessions,
    session_id,
    session_id_of_token,
)
from app.core.config import settings
from app.core.db import get_session
from app.core.rate_limit import Window

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Pairing limits, in the spirit of the email-code ones. A car renews its code every ~10
# minutes and polls every 2 s; several cars can share a carrier's IP, hence the headroom.
pair_starts = Window(30, 3600)  # per IP
pair_polls = Window(120, 60)  # per IP
pair_misses = Window(10, 600)  # per signed-in user: unknown codes looked up or approved


def _location(request: Request) -> str:
    """Roughly where a request comes from, from the headers Cloudflare adds (city and
    region only when the zone's visitor-location headers are on). "" without Cloudflare."""
    parts = [request.headers.get(h, "").strip() for h in ("cf-ipcity", "cf-region", "cf-ipcountry")]
    return ", ".join(p for p in parts if p and p != "XX")


@router.post("/pair/start", response_model=PairStartResponse)
def pair_start(request: Request):
    if not pair_starts.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="too many codes, try again later")
    code, poll_secret = pairings.start(request.headers.get("user-agent", ""), _location(request))
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
def pair_poll(body: PairPollRequest, request: Request, db: Session = Depends(get_session)):
    if not pair_polls.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="too fast")
    status, user_id, user_agent = pairings.poll(body.poll_secret)
    if status != "approved" or user_id is None:
        return PairPollResponse(status=status)
    token = create_session(db, user_id, "pairing", user_agent)
    return signed_in(JSONResponse(PairPollResponse(status="approved").model_dump()), token)


def _check_misses(user: User) -> None:
    # A wrong code is a 404 (not a 401: fail2ban isn't the guard here, this limit is).
    if pair_misses.full(user.id):
        raise HTTPException(status_code=429, detail="too many wrong codes, try again later")


@router.get("/pair/info", response_model=PairInfoResponse)
def pair_info(code: str = Query(""), user: User = Depends(current_user)):
    """Which device shows this code, for the phone to check before approving."""
    _check_misses(user)
    pairing = pairings.pending(code)
    if pairing is None:
        pair_misses.add(user.id)
        raise HTTPException(status_code=404, detail="code not found or expired")
    return PairInfoResponse(device=describe_device(pairing.user_agent), location=pairing.location, asked_at=pairing.created_at)


@router.post("/pair/approve", response_model=OkResponse)
def pair_approve(body: PairApproveRequest, user: User = Depends(current_user)):
    _check_misses(user)
    if not pairings.approve(body.code, user.id):
        pair_misses.add(user.id)
        raise HTTPException(status_code=404, detail="code not found or expired")
    return OkResponse(ok=True)


@router.get("/sessions", response_model=SessionList)
def sessions(request: Request, user: User = Depends(current_user), db: Session = Depends(get_session)):
    """Every browser signed in to this account, most recently used first."""
    mine = session_id_of_token(request.cookies.get(COOKIE_NAME, ""))
    return SessionList(
        sessions=[
            SessionInfo(
                id=session_id(row),
                device=describe_device(row.user_agent),
                via=row.via,
                created_at=row.created_at,
                last_seen_at=row.last_seen_at,
                current=session_id(row) == mine,
            )
            for row in list_sessions(db, user.id)
        ]
    )


@router.delete("/sessions/{sid}", response_model=OkResponse)
def sign_out_session(sid: str, user: User = Depends(current_user), db: Session = Depends(get_session)):
    if not delete_user_session(db, user.id, sid):
        raise HTTPException(status_code=404, detail="no such session")
    return OkResponse(ok=True)


@router.post("/logout-everywhere", response_model=OkResponse)
def logout_everywhere(user: User = Depends(current_user), db: Session = Depends(get_session)):
    """Ends every session of this account, this one included."""
    delete_all_sessions(db, user.id)
    response = JSONResponse(OkResponse(ok=True).model_dump())
    response.headers.append("set-cookie", session_cookie_header("", max_age=0))
    return response
