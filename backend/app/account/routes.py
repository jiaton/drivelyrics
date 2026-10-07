from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.account.service import delete_account
from app.auth.deps import current_user, session_cookie_header
from app.auth.models import User
from app.auth.schemas import OkResponse
from app.core.db import get_session
from app.spotify.routes import accounts, pollers

router = APIRouter(prefix="/api/account", tags=["account"])


@router.delete("", response_model=OkResponse)
def remove_account(user: User = Depends(current_user), session: Session = Depends(get_session)):
    delete_account(session, user.id, accounts, pollers)
    response = JSONResponse(OkResponse(ok=True).model_dump())
    response.headers.append("set-cookie", session_cookie_header("", max_age=0))
    return response
