import pytest
from sqlmodel import Session

from app.auth.models import User
from app.core.db import engine, init_db
from app.feed.limits import BURST, HOUR_MS, TokenBucket, burst_for
from app.feed.schemas import FeedPush, FeedSettingsUpdate
from app.feed.store import FeedStore

from tests.test_feed_runtime import Clock, make_feed

_next_user = iter(range(10_000, 10_100))


@pytest.fixture
def user_id():
    init_db()
    with Session(engine) as db:
        uid = next(_next_user)
        db.add(User(id=uid, email=f"limits-{uid}@example.com", created_at=0))
        db.commit()
        return uid


def test_bucket_allows_a_burst_then_the_hourly_rate():
    bucket = TokenBucket.full(60, 0)
    assert bucket.capacity == BURST
    assert all(bucket.take(0) for _ in range(BURST))
    assert not bucket.take(0)
    assert bucket.next_at(0) == HOUR_MS / 60  # one a minute at 60/hour
    assert not bucket.take(59_000)
    assert bucket.take(60_000)


def test_bucket_refills_only_to_its_capacity():
    bucket = TokenBucket.full(60, 0)
    bucket.take(0)
    assert bucket.available(10 * HOUR_MS) == BURST


def test_a_small_hourly_limit_has_no_bigger_burst():
    assert burst_for(3) == 3
    assert burst_for(0) == 1


def test_lowering_the_rate_keeps_what_is_left_within_the_new_burst():
    bucket = TokenBucket.full(60, 0)
    bucket.set_rate(4, 0)
    assert bucket.available(0) == 4


async def test_screens_are_told_when_the_hourly_limit_stops_fetches(user_id):
    FeedStore().update_settings(user_id, FeedSettingsUpdate(hourly_cap=1))
    clock = Clock()
    feed = make_feed(user_id, clock)
    feed.attach_receiver()
    screen = feed.screens.subscribe()
    await feed._fetch("opened", over_budget=False)
    await feed._fetch("track_ending", over_budget=False)
    assert feed.blocked == "hourly"
    assert screen.get_nowait().notice == "hourly"
    clock.at += HOUR_MS  # a token came back
    await feed._fetch("track_ending", over_budget=False)
    assert feed.blocked == "" and feed.snapshot().notice is None


def test_the_senders_own_limit_shows_until_a_normal_answer(user_id):
    feed = make_feed(user_id)
    feed.on_push(FeedPush(playing=True, title="t", limited="monthly"))
    assert feed.snapshot().notice == "receiver_monthly"
    feed.on_push(FeedPush(playing=True, title="t"))
    assert feed.snapshot().notice is None
