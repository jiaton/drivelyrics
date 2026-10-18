from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from app.auth.deps import current_user
from app.auth.models import User
from app.auth.schemas import OkResponse
from app.core.db import get_session
from app.core.rate_limit import MinInterval
from app.recognize.adapter import AuddRecognizer
from app.recognize.ports import RecognizerError, RecognizerKeyRejected
from app.recognize.schemas import RecognizeResponse, RecognizerKeyStatus, RecognizerKeyUpdate
from app.recognize.service import NoKey, RecognizeService, delete_key, key_status, save_key

router = APIRouter(prefix="/api/recognize", tags=["recognize"])
service = RecognizeService(AuddRecognizer())

MAX_AUDIO_BYTES = 2_000_000  # ~15 s of anything a browser records
_limit = MinInterval(2.0)


@router.get("/key", response_model=RecognizerKeyStatus)
def get_key(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return key_status(session, user.id)


@router.put("/key", response_model=RecognizerKeyStatus)
def put_key(body: RecognizerKeyUpdate, user: User = Depends(current_user), session: Session = Depends(get_session)):
    return save_key(session, user.id, body.token)


@router.delete("/key", response_model=OkResponse)
def remove_key(user: User = Depends(current_user), session: Session = Depends(get_session)):
    delete_key(session, user.id)
    return OkResponse(ok=True)


@router.post("", response_model=RecognizeResponse)
async def recognize(
    audio: UploadFile = File(...),
    clip_ms: int = Form(ge=1000, le=20000),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """A few seconds of sound from the user's microphone → the song and where it was
    when the recording started. The audio goes to AudD with the user's own key and is
    not stored."""
    if not (audio.content_type or "").startswith("audio/"):
        raise HTTPException(status_code=415, detail="expected an audio recording")
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="recording too long")
    if not key_status(session, user.id).configured:  # before the limiter: only real calls count
        raise HTTPException(status_code=409, detail="no recognition key")
    if not _limit.allow(user.id):
        raise HTTPException(status_code=429, detail="one recognition every 2 seconds")
    try:
        # Only the owner's (admin's) unmatched clips are kept, for diagnosing recognition.
        return await service.recognize(session, user.id, data, audio.filename or "clip.webm", clip_ms, keep_failures=user.role == "admin")
    except NoKey:
        raise HTTPException(status_code=409, detail="no recognition key")
    except RecognizerKeyRejected as exc:
        raise HTTPException(status_code=402, detail=f"AudD refused the key: {exc}")
    except RecognizerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
