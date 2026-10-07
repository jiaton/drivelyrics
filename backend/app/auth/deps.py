from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from app.auth.models import User
from app.auth.service import COOKIE_MAX_AGE, COOKIE_NAME, resolve_session
from app.core.config import settings
from app.core.db import get_session


def session_cookie_header(token: str, max_age: int = COOKIE_MAX_AGE) -> str:
    secure = "; Secure" if settings.secure_cookies else ""
    return f"{COOKIE_NAME}={token}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax{secure}"


def optional_user(request: Request, db: Session = Depends(get_session)) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    resolved = resolve_session(db, token)
    if resolved is None:
        return None
    user, refresh = resolved
    if refresh:
        request.state.set_cookie = session_cookie_header(token)  # see SessionCookieMiddleware
    return user


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="not signed in")
    return user


def current_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admins only")
    return user


class SessionCookieMiddleware:
    """Adds a Set-Cookie that a dependency asked for (request.state.set_cookie) to the
    response, whatever kind of response the route returned. FastAPI only merges an
    injected `Response`'s headers into responses it builds itself — not into a
    RedirectResponse or the SSE stream, which is the request a car makes most."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_cookie(message):
            if message["type"] == "http.response.start":
                cookie = scope.get("state", {}).get("set_cookie")
                if cookie:
                    message.setdefault("headers", [])
                    message["headers"] = [*message["headers"], (b"set-cookie", cookie.encode())]
            await send(message)

        await self.app(scope, receive, send_with_cookie)
