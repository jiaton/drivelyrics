"""When to ask the user's side to read their player. Pure: times in, a plan out.

Each fetch costs the user (a Tesla vehicle_data call is billed), so the defaults ask
roughly once per track: when a screen opens, and right after the current track should
have ended — the answer then is already the next track. Skips mid-track are caught by
the user's refresh button (debounced, so skipping several tracks then tapping once is
one fetch) or, if they opt in, a periodic skip check; even without either, the old
track's end-time fetch resynchronises. A paused player is only re-checked if opted in."""

from dataclasses import dataclass

TRACK_END_SLACK_MS = 750  # after the expected end: the next track has started by then
MIN_GAP_MS = 5_000  # automatic fetches are never closer together than this
UNKNOWN_DURATION_MS = 30_000  # playing, no duration given, no skip check: check this often
STALE_END_MS = 10_000  # "should have ended" this long ago: the duration can't be trusted
RESPONSE_TIMEOUT_MS = 15_000  # a fetch not answered within this counts as missed
FIRST_RETRY_MS = 30_000
LATER_RETRY_MS = 60_000


@dataclass
class Track:
    key: str
    title: str | None
    artist: str | None
    album: str | None
    duration_ms: int | None
    position_ms: int
    playing: bool
    source: str | None
    measured_ms: float  # server-clock unix ms at which position_ms was true

    def position_at(self, now_ms: float) -> int:
        if not self.playing:
            return self.position_ms
        return max(0, int(self.position_ms + now_ms - self.measured_ms))


@dataclass
class Plan:
    at_ms: float
    reason: str


def plan_next(
    now_ms: float, track: Track | None, last_fetch_ms: float, missed: int, skip_check_s: int, paused_check_s: int
) -> Plan | None:
    """The next automatic fetch, or None for "nothing to ask until something happens"."""
    plans: list[Plan] = []
    if missed:
        plans.append(Plan(last_fetch_ms + (FIRST_RETRY_MS if missed == 1 else LATER_RETRY_MS), "retry"))
    if track is not None and track.playing:
        # An absolute time, from when the position was measured: recomputing it from
        # "now" would slide it forward forever once the track had passed its end.
        end_ms = track.measured_ms + track.duration_ms - track.position_ms if track.duration_ms else None
        trusted_end = end_ms is not None and now_ms - end_ms < STALE_END_MS
        already_asked = end_ms is not None and last_fetch_ms >= end_ms + TRACK_END_SLACK_MS
        if trusted_end and not already_asked:
            plans.append(Plan(end_ms + TRACK_END_SLACK_MS, "track_ending"))
        elif not skip_check_s:
            plans.append(Plan(last_fetch_ms + UNKNOWN_DURATION_MS, "skip_check"))
        if skip_check_s:
            plans.append(Plan(last_fetch_ms + skip_check_s * 1000, "skip_check"))
    elif track is not None and paused_check_s:
        plans.append(Plan(last_fetch_ms + paused_check_s * 1000, "paused_check"))
    if not plans:
        return None
    first = min(plans, key=lambda p: p.at_ms)
    return Plan(max(first.at_ms, last_fetch_ms + MIN_GAP_MS), first.reason)
