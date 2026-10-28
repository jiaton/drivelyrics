"""Linking a receiver without copying a token (2026-10-28, owner: "one-click setup").

The receiver — the Home Assistant integration, say — asks for a link code, shows the
user a URL with it, and polls with a secret only it holds. The user opens the URL signed
in and approves; the next poll hands the receiver a new feed token for that user, once.
Same shape as car pairing (auth/service.PairingRegistry) and OAuth's device flow: the
receiver never sees a password or a session, the user never sees the token. In memory:
a restart just means starting the link again."""

import hashlib
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

LINK_TTL_SECONDS = 600
POLL_INTERVAL_SECONDS = 3
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I lookalikes
_CODE_LENGTH = 8
_MAX_PENDING = 500

LinkStatus = Literal["pending", "approved", "denied", "expired"]


@dataclass
class _Link:
    code: str
    poll_secret_hash: str
    client_name: str
    created_at: float
    status: LinkStatus = "pending"
    token: str | None = None  # set on approval, handed out by the next poll, then dropped


@dataclass
class LinkRegistry:
    clock: Callable[[], float] = time.time
    _by_code: dict[str, _Link] = field(default_factory=dict)

    def start(self, client_name: str) -> tuple[str, str]:
        """(code, poll_secret). The code is shown to the user; the secret stays with the
        receiver."""
        self._prune()
        while len(self._by_code) >= _MAX_PENDING:
            del self._by_code[next(iter(self._by_code))]
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        poll_secret = secrets.token_urlsafe(32)
        self._by_code[code] = _Link(code, _hash(poll_secret), client_name, self.clock())
        return code, poll_secret

    def pending(self, code: str) -> _Link | None:
        """The link a user is about to approve, if it can still be approved."""
        self._prune()
        link = self._by_code.get(normalize_code(code))
        return link if link is not None and link.status == "pending" else None

    def approve(self, code: str, token: str) -> bool:
        link = self.pending(code)
        if link is None:
            return False
        link.status, link.token = "approved", token
        return True

    def deny(self, code: str) -> bool:
        link = self.pending(code)
        if link is None:
            return False
        link.status = "denied"
        return True

    def poll(self, poll_secret: str) -> tuple[LinkStatus, str | None]:
        """(status, token). A decision is handed out once; the link is gone after that."""
        self._prune()
        wanted = _hash(poll_secret)
        for code, link in self._by_code.items():
            if secrets.compare_digest(link.poll_secret_hash, wanted):
                if link.status == "pending":
                    return "pending", None
                del self._by_code[code]
                return link.status, link.token
        return "expired", None

    def _prune(self) -> None:
        now = self.clock()
        for code in [c for c, link in self._by_code.items() if now - link.created_at > LINK_TTL_SECONDS]:
            del self._by_code[code]


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def display_code(code: str) -> str:
    """ABCD-EFGH: easier to compare by eye."""
    return f"{code[:4]}-{code[4:]}"


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()
