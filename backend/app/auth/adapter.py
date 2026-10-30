import logging
from urllib.parse import urlencode

import httpx

from app.auth.ports import GitHubIdentity, GitHubOAuthPort, GoogleIdentity, GoogleOAuthPort, MailerPort
from app.core.config import settings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"

RESEND_URL = "https://api.resend.com/emails"

log = logging.getLogger(__name__)


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


class GitHubOAuthClient(GitHubOAuthPort):
    def build_authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "user:email",
            "state": state,
            "allow_signup": "true",
        }
        return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

    async def identify(self, code: str, redirect_uri: str) -> GitHubIdentity:
        # Kept: the user id, the verified primary email and the display name (or the
        # login when there is none). Nothing else of the profile.
        async with httpx.AsyncClient(timeout=10) as client:
            token = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            token.raise_for_status()
            access_token = token.json().get("access_token")
            if not access_token:  # GitHub answers 200 with {"error": …} for a bad code
                raise httpx.HTTPStatusError("no access token", request=token.request, response=token)
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
            user = await client.get(f"{GITHUB_API}/user", headers=headers)
            user.raise_for_status()
            emails = await client.get(f"{GITHUB_API}/user/emails", headers=headers)
            emails.raise_for_status()
        body = user.json()
        primary = next((e["email"] for e in emails.json() if e.get("primary") and e.get("verified")), "")
        return GitHubIdentity(id=str(body["id"]), email=primary, name=body.get("name") or body.get("login") or "")


class ResendMailer(MailerPort):
    """Plain-text mail through Resend's HTTP API."""

    @property
    def enabled(self) -> bool:
        return bool(settings.resend_api_key and settings.mail_from)

    async def send(self, to: str, subject: str, body: str) -> bool:
        payload = {"from": settings.mail_from, "to": [to], "subject": subject, "text": body}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(RESEND_URL, json=payload, headers={"Authorization": f"Bearer {settings.resend_api_key}"})
        except httpx.HTTPError as exc:
            log.warning("sign-in mail failed: %s", type(exc).__name__)
            return False
        if r.status_code >= 300:
            log.warning("sign-in mail refused: HTTP %s %s", r.status_code, r.text[:200])
            return False
        return True
