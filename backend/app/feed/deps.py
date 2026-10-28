from fastapi import Header, HTTPException

from app.feed.store import FeedStore

_store = FeedStore()


def bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def feed_user(authorization: str | None = Header(default=None)) -> int:
    """The user a feed token belongs to (Authorization: Bearer dlf_…). Feed tokens only
    authenticate the public feed endpoints, never the rest of the API."""
    token = bearer_token(authorization)
    user_id = _store.user_for_token(token) if token else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="missing or unknown feed token", headers={"WWW-Authenticate": "Bearer"})
    return user_id
