from urllib.parse import urlencode

import httpx

from app.auth.ports import GoogleIdentity, GoogleOAuthPort
from app.core.config import settings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthClient(GoogleOAuthPort):
    def build_authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    async def identify(self, code: str, redirect_uri: str) -> GoogleIdentity:
        # Only the email (identity) and name are kept: the profile picture Google also
        # returns is deliberately dropped — the landing and privacy pages promise
        # "email and name, nothing else".
        # The userinfo call (over TLS, with the token Google just issued us) stands in
        # for verifying the ID token's signature locally — same trust, no JWKS handling.
        async with httpx.AsyncClient(timeout=10) as client:
            token = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                },
            )
            token.raise_for_status()
            info = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {token.json()['access_token']}"})
            info.raise_for_status()
            body = info.json()
        return GoogleIdentity(
            sub=body["sub"],
            email=body.get("email", ""),
            email_verified=bool(body.get("email_verified")),
            name=body.get("name", ""),
        )
