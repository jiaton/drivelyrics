from app.feed import schedule
from app.feed.schedule import Track, plan_next

NOW = 1_000_000.0


def track(**kw) -> Track:
    base = dict(key="k", title="t", artist="a", album=None, duration_ms=200_000, position_ms=50_000, playing=True, source=None, measured_ms=NOW)
    return Track(**(base | kw))


def test_playing_with_duration_asks_right_after_the_track_ends():
    plan = plan_next(NOW, track(), last_fetch_ms=NOW - 60_000, missed=0, skip_check_s=0, paused_check_s=0)
    assert plan.reason == "track_ending"
    assert plan.at_ms == NOW + 150_000 + schedule.TRACK_END_SLACK_MS


def test_position_is_extrapolated_from_when_it_was_measured():
    plan = plan_next(NOW, track(measured_ms=NOW - 10_000), NOW - 60_000, 0, 0, 0)
    assert plan.at_ms == NOW + 140_000 + schedule.TRACK_END_SLACK_MS


def test_skip_check_comes_first_when_sooner():
    plan = plan_next(NOW, track(), last_fetch_ms=NOW, missed=0, skip_check_s=30, paused_check_s=0)
    assert (plan.reason, plan.at_ms) == ("skip_check", NOW + 30_000)


def test_paused_is_left_alone_unless_opted_in():
    assert plan_next(NOW, track(playing=False), NOW, 0, 0, 0) is None
    plan = plan_next(NOW, track(playing=False), NOW, 0, 0, 120)
    assert (plan.reason, plan.at_ms) == ("paused_check", NOW + 120_000)


def test_unknown_or_untrustworthy_duration_falls_back_to_a_slow_check():
    assert plan_next(NOW, track(duration_ms=None), NOW, 0, 0, 0).at_ms == NOW + schedule.UNKNOWN_DURATION_MS
    overrun = track(position_ms=250_000)  # 50 s past its end: the duration is wrong
    assert plan_next(NOW, overrun, NOW, 0, 0, 0).reason == "skip_check"


def test_unanswered_fetches_back_off():
    assert plan_next(NOW, None, NOW, missed=1, skip_check_s=0, paused_check_s=0).at_ms == NOW + schedule.FIRST_RETRY_MS
    assert plan_next(NOW, None, NOW, missed=3, skip_check_s=0, paused_check_s=0).at_ms == NOW + schedule.LATER_RETRY_MS
    assert plan_next(NOW, None, NOW, 0, 0, 0) is None


def test_never_two_automatic_fetches_closer_than_the_minimum_gap():
    ending = track(position_ms=199_900)
    plan = plan_next(NOW, ending, last_fetch_ms=NOW - 1_000, missed=0, skip_check_s=0, paused_check_s=0)
    assert plan.at_ms == NOW - 1_000 + schedule.MIN_GAP_MS


def test_track_end_is_a_fixed_time_and_asked_about_once():
    t = track(position_ms=199_000)  # ends at NOW + 1 s
    first = plan_next(NOW, t, last_fetch_ms=NOW - 60_000, missed=0, skip_check_s=0, paused_check_s=0)
    later = plan_next(NOW + 500, t, last_fetch_ms=NOW - 60_000, missed=0, skip_check_s=0, paused_check_s=0)
    assert first.at_ms == later.at_ms == NOW + 1_000 + schedule.TRACK_END_SLACK_MS
    # Asked after that end and the answer was the same track still at its end: don't
    # keep asking about the same end, fall back to the slow check.
    asked = plan_next(NOW + 2_000, t, last_fetch_ms=NOW + 1_800, missed=0, skip_check_s=0, paused_check_s=0)
    assert asked.reason == "skip_check"
