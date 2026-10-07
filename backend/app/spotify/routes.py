import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sse_starlette.sse import EventSourceResponse

from app.auth.deps import current_user, optional_user
from app.auth.models import User
from app.spotify.adapter import SpotifyApiClient
from app.spotify.ports import SpotifyAuthError
from app.spotify.schemas import NowPlayingResponse, SpotifyAppRequest, SpotifyStatusResponse
from app.spotify.service import DISCONNECTED, REDIRECT_URI, RESUBSCRIBE, PollerRegistry, SpotifyAccounts, pending_states

router = APIRouter(prefix="/api/spotify", tags=["spotify"])
client = SpotifyApiClient()
accounts = SpotifyAccounts()
pollers = PollerRegistry(client, accounts)


def _status(user_id: int) -> SpotifyStatusResponse:
    s = accounts.status(user_id)
    return SpotifyStatusResponse(app_configured=s.app_configured, client_id=s.client_id, connected=s.connected, redirect_uri=REDIRECT_URI)


@router.get("/status", response_model=SpotifyStatusResponse)
def status(user: User = Depends(current_user)):
    return _status(user.id)


@router.put("/app", response_model=SpotifyStatusResponse)
def save_app(body: SpotifyAppRequest, user: User = Depends(current_user)):
    accounts.save_app(user.id, body.client_id, body.client_secret)
    pollers.restart(user.id)
    return _status(user.id)


@router.delete("/app", response_model=SpotifyStatusResponse)
def remove_app(user: User = Depends(current_user)):
    accounts.remove_app(user.id)
    pollers.restart(user.id)
    return _status(user.id)


@router.get("/connect")
def connect(user: User = Depends(current_user)):
    creds = accounts.credentials(user.id)
    if creds is None:
        raise HTTPException(status_code=409, detail="add your Spotify app first")
    return RedirectResponse(client.build_authorize_url(creds, pending_states.issue(user.id), REDIRECT_URI))


@router.get("/callback")
async def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user: User | None = Depends(optional_user),
):
    state_user = pending_states.consume(state) if state else None
    # The state names who started the link; the browser finishing it must be them.
    if error or not code or state_user is None or user is None or user.id != state_user:
        return RedirectResponse("/?spotify=failed")
    creds = accounts.credentials(user.id)
    if creds is None:
        return RedirectResponse("/?spotify=failed")
    try:
        bundle = await client.exchange_code(creds, code, REDIRECT_URI)
    except SpotifyAuthError:
        return RedirectResponse("/?spotify=bad-credentials")
    accounts.save_token(user.id, bundle)
    pollers.restart(user.id)
    return RedirectResponse("/?spotify=connected")


@router.get("/now-playing/stream")
async def now_playing_stream(user: User = Depends(current_user)):
    poller, queue = pollers.subscribe(user.id)

    async def events():
        try:
            while True:
                state = await queue.get()
                if state == DISCONNECTED:
                    yield {"event": "spotify-disconnected", "data": "{}"}
                    return
                if state == RESUBSCRIBE:
                    return
                payload = NowPlayingResponse.model_validate(state, from_attributes=True)
                yield {"event": "now-playing", "data": payload.model_dump_json()}
        except asyncio.CancelledError:
            raise
        finally:
            poller.broadcaster.unsubscribe(queue)

    return EventSourceResponse(events())
