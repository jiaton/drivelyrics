from dataclasses import dataclass
from typing import Protocol


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str


class GoogleOAuthPort(Protocol):
    """Plain OpenID sign-in: scopes openid/email/profile only, no Google API access."""

    def build_authorize_url(self, state: str, redirect_uri: str) -> str: ...

    async def identify(self, code: str, redirect_uri: str) -> GoogleIdentity: ...
