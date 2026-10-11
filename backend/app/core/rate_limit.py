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
