"""Signing in a device without a keyboard (a car): a code on its screen, approved by a phone."""

import hashlib
import secrets
import time
from dataclasses import dataclass, field


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# The car shows a QR code (and the same short code as text); a phone that's already
# signed in opens it and approves; the car, polling with a secret only it holds, then
# receives its own session cookie. Nothing is typed in the car and Google sign-in never
# runs in the car's browser.

PAIR_TTL_SECONDS = 600
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I lookalikes
_CODE_LENGTH = 6
_MAX_PENDING_PAIRINGS = 500


@dataclass
class _Pairing:
    code: str
    poll_secret_hash: str
    created_at: float
    approved_user_id: int | None = None
    user_agent: str = ""
    location: str = ""  # where the asking device is, from its IP (Cloudflare's headers)


@dataclass
class PairingRegistry:
    _by_code: dict[str, _Pairing] = field(default_factory=dict)

    def start(self, user_agent: str = "", location: str = "") -> tuple[str, str]:
        """Returns (code, poll_secret). The code is public (it's on screen); the poll
        secret never leaves the requesting browser."""
        self._prune()
        while len(self._by_code) >= _MAX_PENDING_PAIRINGS:
            del self._by_code[next(iter(self._by_code))]
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        poll_secret = secrets.token_urlsafe(32)
        self._by_code[code] = _Pairing(code, _hash(poll_secret), time.time(), user_agent=user_agent[:200], location=location[:120])
        return code, poll_secret

    def pending(self, code: str) -> _Pairing | None:
        """The pairing waiting for approval under this code, for the approve page to say
        which device is asking."""
        self._prune()
        pairing = self._by_code.get(normalize_code(code))
        return pairing if pairing is not None and pairing.approved_user_id is None else None

    def approve(self, code: str, user_id: int) -> bool:
        self._prune()
        pairing = self._by_code.get(normalize_code(code))
        if pairing is None or pairing.approved_user_id is not None:
            return False
        pairing.approved_user_id = user_id
        return True

    def poll(self, poll_secret: str) -> tuple[str, int | None, str]:
        """("pending" | "approved" | "expired", user_id, user_agent). Approval is handed
        out once; the pairing is gone after that."""
        self._prune()
        wanted = _hash(poll_secret)
        for code, pairing in self._by_code.items():
            if secrets.compare_digest(pairing.poll_secret_hash, wanted):
                if pairing.approved_user_id is None:
                    return "pending", None, ""
                del self._by_code[code]
                return "approved", pairing.approved_user_id, pairing.user_agent
        return "expired", None, ""

    def _prune(self) -> None:
        now = time.time()
        for code in [c for c, p in self._by_code.items() if now - p.created_at > PAIR_TTL_SECONDS]:
            del self._by_code[code]


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


pairings = PairingRegistry()
