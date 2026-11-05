import math
import time
from collections.abc import Hashable


class MinInterval:
    """At most one call per `seconds` for each key. In memory, per process: enough to
    keep one user's screen from hammering a provider, not a security boundary."""

    def __init__(self, seconds: float, max_keys: int = 10_000) -> None:
        self._seconds = seconds
        self._max_keys = max_keys
        self._last: dict[Hashable, float] = {}

    def allow(self, key: Hashable) -> bool:
        now = time.monotonic()
        if now - self._last.get(key, -math.inf) < self._seconds:
            return False
        if len(self._last) >= self._max_keys:
            self._last.clear()
        self._last[key] = now
        return True


class Window:
    """At most `limit` events per key within `seconds` (a sliding window). In memory, per
    process, like MinInterval; used where a guess or a flood has to be stopped."""

    def __init__(self, limit: int, seconds: float, max_keys: int = 10_000) -> None:
        self._limit = limit
        self._seconds = seconds
        self._max_keys = max_keys
        self._events: dict[Hashable, list[float]] = {}

    def full(self, key: Hashable) -> bool:
        now = time.monotonic()
        recent = [at for at in self._events.get(key, []) if now - at < self._seconds]
        if recent:
            self._events[key] = recent
        else:
            self._events.pop(key, None)
        return len(recent) >= self._limit

    def add(self, key: Hashable) -> None:
        if key not in self._events and len(self._events) >= self._max_keys:
            self._events.clear()
        self._events.setdefault(key, []).append(time.monotonic())

    def allow(self, key: Hashable) -> bool:
        """Counts this event and says whether it was within the limit."""
        if self.full(key):
            return False
        self.add(key)
        return True
