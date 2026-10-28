"""The hourly limit on fetches, as a token bucket: a burst of a few at once (opening a
screen, skipping tracks and tapping refresh), then `per_hour` an hour on average.
Each fetch may cost the user money (a Tesla vehicle_data read is billed), so this is
the steady-state cap; the monthly budget is the total."""

from dataclasses import dataclass

BURST = 10  # fetches that may go out back to back
HOUR_MS = 3_600_000


@dataclass
class TokenBucket:
    per_hour: int
    tokens: float
    at_ms: float

    @classmethod
    def full(cls, per_hour: int, now_ms: float) -> "TokenBucket":
        return cls(per_hour, float(burst_for(per_hour)), now_ms)

    @property
    def capacity(self) -> int:
        return burst_for(self.per_hour)

    def _refill(self, now_ms: float) -> None:
        if now_ms > self.at_ms:
            self.tokens = min(self.capacity, self.tokens + (now_ms - self.at_ms) * self.per_hour / HOUR_MS)
        self.at_ms = max(self.at_ms, now_ms)

    def available(self, now_ms: float) -> int:
        self._refill(now_ms)
        return int(self.tokens)

    def take(self, now_ms: float) -> bool:
        self._refill(now_ms)
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True

    def next_at(self, now_ms: float) -> float:
        """When the next fetch may go out (now, if one may)."""
        self._refill(now_ms)
        if self.tokens >= 1:
            return now_ms
        return now_ms + (1 - self.tokens) * HOUR_MS / self.per_hour

    def set_rate(self, per_hour: int, now_ms: float) -> None:
        self._refill(now_ms)
        self.per_hour = per_hour
        self.tokens = min(self.tokens, self.capacity)


def burst_for(per_hour: int) -> int:
    return max(1, min(BURST, per_hour))
