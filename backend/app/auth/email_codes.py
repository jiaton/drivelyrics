"""Sign-in codes sent by email."""

import hashlib
import secrets
import time
from dataclasses import dataclass, field


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# Six digits, valid 10 minutes, five tries; then a new code has to be sent. Sending is
# limited per address, per visitor IP and overall (the mail service's daily quota), so
# the form can't be used to flood someone's inbox. In memory: a restart just means
# "send a new code".

EMAIL_CODE_TTL_SECONDS = 600
EMAIL_CODE_TRIES = 5
EMAIL_RESEND_AFTER = 60
_EMAIL_PER_ADDRESS_HOUR = 5
_EMAIL_PER_IP_HOUR = 10
_EMAIL_PER_DAY = 90  # Resend's free plan sends 100 a day
_MAX_PENDING_CODES = 1000


class TooSoon(Exception):
    pass


@dataclass
class _EmailCode:
    code_hash: str
    created_at: float
    tries_left: int = EMAIL_CODE_TRIES


@dataclass
class EmailCodes:
    _by_email: dict[str, _EmailCode] = field(default_factory=dict)
    _sent: list[tuple[float, str, str]] = field(default_factory=list)  # (at, email, ip)

    def issue(self, email: str, ip: str) -> str:
        """A new code for the address (replacing any earlier one). TooSoon when a limit
        is reached."""
        now = time.time()
        self._prune(now)
        hour = [(e, i) for at, e, i in self._sent if now - at < 3600]
        last = max((at for at, e, _ in self._sent if e == email), default=0.0)
        if (
            now - last < EMAIL_RESEND_AFTER
            or sum(e == email for e, _ in hour) >= _EMAIL_PER_ADDRESS_HOUR
            or (ip and sum(i == ip for _, i in hour) >= _EMAIL_PER_IP_HOUR)
            or len(self._sent) >= _EMAIL_PER_DAY
        ):
            raise TooSoon
        while len(self._by_email) >= _MAX_PENDING_CODES:
            del self._by_email[next(iter(self._by_email))]
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._by_email[email] = _EmailCode(_hash(f"{email}:{code}"), now)
        self._sent.append((now, email, ip))
        return code

    def withdraw(self, email: str) -> None:
        """The mail didn't go out: the code is useless, but the send still counts."""
        self._by_email.pop(email, None)

    def check(self, email: str, code: str) -> bool:
        """True once for the right code; a wrong one uses up a try."""
        self._prune(time.time())
        entry = self._by_email.get(email)
        if entry is None:
            return False
        if secrets.compare_digest(entry.code_hash, _hash(f"{email}:{code.strip()}")):
            del self._by_email[email]
            return True
        entry.tries_left -= 1
        if entry.tries_left <= 0:
            del self._by_email[email]
        return False

    def _prune(self, now: float) -> None:
        for email in [e for e, c in self._by_email.items() if now - c.created_at > EMAIL_CODE_TTL_SECONDS]:
            del self._by_email[email]
        self._sent = [s for s in self._sent if now - s[0] < 86_400]


email_codes = EmailCodes()
