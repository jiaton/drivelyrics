import secrets
import time
from typing import Generic, TypeVar

T = TypeVar("T")


class OneTimeStates(Generic[T]):
    """Single-use, expiring tokens carrying a payload — the OAuth `state` param (CSRF
    protection on the callback leg) for both Google and Spotify. In-memory: one process,
    and a state lost to a restart just means "start the sign-in again".

    TTL is generous because what's being timed is a human on a consent screen, not a
    network round trip: a 10-minute TTL rejected a real first Spotify link after 11
    minutes (2026-09-12). Don't tighten without re-checking that."""

    def __init__(self, ttl_seconds: float = 1800, max_pending: int = 1000) -> None:
        self._ttl = ttl_seconds
        self._max = max_pending
        self._issued: dict[str, tuple[float, T]] = {}

    def issue(self, payload: T) -> str:
        self._prune()
        state = secrets.token_urlsafe(24)
        self._issued[state] = (time.time(), payload)
        return state

    def consume(self, state: str) -> T | None:
        entry = self._issued.pop(state, None)
        if entry is None or time.time() - entry[0] > self._ttl:
            return None
        return entry[1]

    def _prune(self) -> None:
        now = time.time()
        for key in [k for k, (at, _) in self._issued.items() if now - at > self._ttl]:
            del self._issued[key]
        while len(self._issued) >= self._max:  # unauthenticated callers can issue these
            del self._issued[next(iter(self._issued))]
