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


@dataclass
class GitHubIdentity:
    id: str
    email: str  # the primary email, "" unless GitHub has verified it
    name: str


class GitHubOAuthPort(Protocol):
    """GitHub OAuth App sign-in: scope user:email only (to read the verified primary
    email), no repository or other access."""

    def build_authorize_url(self, state: str, redirect_uri: str) -> str: ...

    async def identify(self, code: str, redirect_uri: str) -> GitHubIdentity: ...


class MailerPort(Protocol):
    @property
    def enabled(self) -> bool: ...

    async def send(self, to: str, subject: str, body: str) -> bool:
        """True once the mail service accepted it."""
        ...
