import asyncio
from collections import Counter

import pytest
from sqlmodel import Session

from app.auth.models import User
from app.core.db import engine, init_db
from app.feed import schedule
from app.feed import service as feed_service
from app.feed.schemas import DeliveryResult, FeedPush, FeedSettingsUpdate
from app.feed.service import RefreshRefused, UserFeed, track_key
from app.feed.store import FeedStore, month_of

_next_user = iter(range(9000, 10000))


@pytest.fixture
def user_id():
    init_db()  # idempotent; these tests run without the app's startup
    with Session(engine) as db:
        uid = next(_next_user)
        db.add(User(id=uid, email=f"rt-{uid}@example.com", created_at=0))
        db.commit()
        return uid


class Clock:
    def __init__(self, at=1_760_000_000_000.0):
        self.at = at

    def __call__(self):
        return self.at


class FakeSender:
    def __init__(self, ok=True):
        self.ok = ok
        self.sent: list[tuple[str, bytes]] = []

    async def check(self, url):
        return None

    async def deliver(self, url, secret, body, event_type):
        self.sent.append((event_type, body))
        return DeliveryResult(ok=self.ok, detail="HTTP 200" if self.ok else "HTTP 500")


def make_feed(user_id, clock=None, sender=None):
    return UserFeed(user_id, FeedStore(), sender or FakeSender(), Counter(), clock or Clock())


def test_track_key_ignores_script_case_and_artist_order():
    assert track_key("後來", "劉若英") == track_key("后来", "刘若英")
    assert track_key("Song", "A, B") == track_key("song", "B, A")
    assert track_key("Song", "A") != track_key("Song", "B")


def test_push_sets_what_screens_see(user_id):
    clock = Clock()
    feed = make_feed(user_id, clock)
    feed.on_push(FeedPush(playing=True, title="富士山下", artist="陳奕迅", duration_ms=259_000, position_ms=81_000))
    clock.at += 2_000
    snap = feed.snapshot()
    assert (snap.is_playing, snap.name, snap.progress_ms, snap.source) == (True, "富士山下", 83_000, "feed")
    assert snap.track_id == track_key("富士山下", "陳奕迅")


def test_measured_at_is_trusted_only_near_the_server_clock(user_id):
    clock = Clock()
    feed = make_feed(user_id, clock)
    feed.on_push(FeedPush(playing=True, title="t", position_ms=10_000, measured_at=int(clock.at) - 3_000))
    assert feed.snapshot().progress_ms == 13_000
    feed.on_push(FeedPush(playing=True, title="t", position_ms=10_000, measured_at=int(clock.at) - 3_600_000))
    assert feed.snapshot().progress_ms == 10_000  # an hour off: ignored


def test_a_track_without_updates_stops_after_its_end(user_id):
    clock = Clock()
    feed = make_feed(user_id, clock)
    feed.on_push(FeedPush(playing=True, title="t", duration_ms=60_000, position_ms=0))
    clock.at += 60_000 + feed_service.OVERRUN_MS + 1
    assert not feed.snapshot().is_playing
    clock.at += feed_service.STALE_TRACK_MS
    assert feed.snapshot().track_id is None  # long gone: nothing playing


def test_push_without_title_keeps_the_track(user_id):
    feed = make_feed(user_id)
    feed.on_push(FeedPush(playing=True, title="t", artist="a", position_ms=5_000))
    feed.on_push(FeedPush(playing=False))
    snap = feed.snapshot()
    assert (snap.name, snap.artist, snap.is_playing) == ("t", "a", False)


async def test_fetch_reaches_receivers_counts_usage_and_respects_the_hourly_cap(user_id):
    clock = Clock()
    store = FeedStore()
    store.update_settings(user_id, FeedSettingsUpdate(hourly_cap=2))
    feed = make_feed(user_id, clock)
    queue = feed.attach_receiver()
    for _ in range(3):
        await feed._fetch("refresh", over_budget=False)
        clock.at += 6_000
    assert queue.qsize() == 2 and feed.blocked == "hourly"
    assert store.fetches(user_id, month_of(clock.at / 1000)) == 2


async def test_monthly_budget_blocks_unless_confirmed(user_id):
    store = FeedStore()
    store.update_settings(user_id, FeedSettingsUpdate(monthly_budget=0))
    feed = make_feed(user_id)
    queue = feed.attach_receiver()
    await feed._fetch("track_ending", over_budget=False)
    assert queue.empty() and feed.blocked == "monthly"
    with pytest.raises(RefreshRefused) as refused:
        feed.request_refresh(confirm_over_budget=False)
    assert refused.value.reason == "monthly"
    await feed._fetch("refresh", over_budget=True)
    assert queue.qsize() == 1


async def test_undelivered_fetch_is_not_counted_or_awaited(user_id):
    feed = make_feed(user_id)
    await feed._fetch("opened", over_budget=False)  # no receiver, no webhook
    assert feed.last_event.delivered is False
    assert feed._awaiting is None and FeedStore().fetches(user_id, month_of(feed._clock() / 1000)) == 0


async def test_webhook_pauses_after_repeated_failures(user_id):
    store = FeedStore()
    store.set_webhook(user_id, "https://hook.example.com/x")
    sender = FakeSender(ok=False)
    feed = make_feed(user_id, sender=sender)
    for _ in range(feed_service.WEBHOOK_PAUSE_AFTER):
        await feed._fetch("refresh", over_budget=True)
        feed._clock.at += 6_000
    assert store.webhook(user_id).paused
    assert feed.webhook_state()[0] == "paused"


def test_refresh_is_debounced_and_rate_limited(user_id):
    clock = Clock()
    feed = make_feed(user_id, clock)
    feed.request_refresh(False)
    first = feed._soon.at_ms
    clock.at += 500
    feed.request_refresh(False)  # absorbed by the pending one
    assert feed._soon.at_ms == first
    feed._soon = None
    with pytest.raises(RefreshRefused) as refused:
        feed.request_refresh(False)
    assert refused.value.reason == "too_soon"


async def test_scheduler_end_to_end(user_id, monkeypatch):
    """Real loop, shortened timings: opened → push → track_ending right after the track
    → screen closes → stop."""
    monkeypatch.setattr(schedule, "MIN_GAP_MS", 100)
    monkeypatch.setattr(schedule, "TRACK_END_SLACK_MS", 50)
    monkeypatch.setattr(feed_service, "GRACE_MS", 300)
    monkeypatch.setattr(feed_service, "TICK_MS", 50)
    feed = UserFeed(user_id, FeedStore(), FakeSender(), Counter())
    receiver = feed.attach_receiver()
    screen = feed.subscribe_screen()
    feed.start()

    async def next_event():
        return await asyncio.wait_for(receiver.get(), 3)

    kind, body = await next_event()
    assert kind == "fetch" and '"opened"' in body
    feed.on_push(FeedPush(playing=True, title="short", duration_ms=400, position_ms=0))
    kind, body = await next_event()
    assert kind == "fetch" and '"track_ending"' in body
    feed.screens.unsubscribe(screen)
    kind, body = await next_event()
    assert kind == "stop"
    await asyncio.wait_for(feed.task, 3)
    assert feed.stopped == "unwatched"
