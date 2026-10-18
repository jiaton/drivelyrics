"""The now-playing feed at run time: one UserFeed per user holding what they last
pushed, the screens watching it, the event-stream connections of their side, and — while
a screen is open — a scheduler deciding when to ask for the next update (schedule.py).

Stop reasons are kept apart (template rule for background work): the scheduler ends
because nobody watches any more, because the user's feed was turned off or replaced,
because it crashed, or because the server is shutting down."""

import asyncio
import collections
import contextlib
import logging
import secrets
import time
from collections import Counter
from enum import Enum

from app.core.nowplaying import RESUBSCRIBE, Broadcaster, NowPlaying
from app.feed.ports import WebhookSenderPort
from app.feed.schedule import RESPONSE_TIMEOUT_MS, Plan, Track, plan_next
from app.feed.schemas import EventLog, FeedPush, FeedPushAck, FeedStatusResponse, FetchEvent, FetchReason, PingEvent, PushLog, StopEvent
from app.feed.store import FeedStore, month_of
from app.lyrics.matching import text_track_id as track_key

log = logging.getLogger(__name__)

GRACE_MS = 60_000  # like the Spotify poller: outlive the last screen briefly (reloads)
TICK_MS = 5_000  # the loop re-checks at least this often (watchers, timeouts)
REFRESH_DEBOUNCE_MS = 1_500  # several taps (or skips then a tap) become one fetch
REFRESH_MIN_INTERVAL_MS = 5_000
RECEIVER_LIMIT = 3  # event-stream connections per user
RECEIVER_QUEUE = 8
STALE_TRACK_MS = 10 * 60_000  # a track pushed longer ago than this isn't shown on (re)open
OVERRUN_MS = 20_000  # past the track's end by this much with no update: show it stopped
CLOCK_TRUST_MS = 5 * 60_000  # a client's measured_at further off the server clock is ignored
WEBHOOK_PAUSE_AFTER = 10  # consecutive failures


class StopReason(str, Enum):
    UNWATCHED = "unwatched"
    DISABLED = "disabled"
    CRASHED = "crashed"
    SHUTDOWN = "shutdown"


class RefreshRefused(Exception):
    def __init__(self, reason: str) -> None:  # "too_soon" | "hourly" | "monthly"
        super().__init__(reason)
        self.reason = reason


class TooManyReceivers(Exception):
    pass


def _now_ms() -> float:
    return time.time() * 1000


class UserFeed:
    def __init__(self, user_id: int, store: FeedStore, sender: WebhookSenderPort, counters: Counter[str], clock=_now_ms) -> None:
        self.user_id = user_id
        self.screens = Broadcaster()
        self.receivers: set[asyncio.Queue] = set()
        self.track: Track | None = None
        self.task: asyncio.Task | None = None
        self._store = store
        self._sender = sender
        self._counters = counters
        self._clock = clock
        self._wake = asyncio.Event()
        self._cancel_reason = StopReason.SHUTDOWN
        self._last_fetch_ms = 0.0
        self._awaiting: tuple[str, float] | None = None  # (fetch id, sent at) until answered
        self._missed = 0
        self._soon: Plan | None = None  # a refresh, or a fetch for a newly connected receiver
        self._soon_over_budget = False
        self._last_refresh_request_ms = 0.0
        self._hour: collections.deque[float] = collections.deque()
        self._blocked_until = 0.0
        self._webhook_failures = 0
        # Status, for the settings page.
        self.blocked = ""
        self.last_event: EventLog | None = None
        self.last_push: PushLog | None = None
        self.webhook_detail = ""
        self.stopped = ""

    # --- what screens see ---------------------------------------------------------

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    @property
    def watching(self) -> bool:
        return self.running and self.screens.subscriber_count > 0

    def snapshot(self) -> NowPlaying:
        now = self._clock()
        track = self.track
        if track is None or now - track.measured_ms > STALE_TRACK_MS:
            return NowPlaying(False, None, None, None, None, None, None, now / 1000, source="feed")
        position = track.position_at(now)
        playing = track.playing
        if playing and track.duration_ms and position > track.duration_ms + OVERRUN_MS:
            playing, position = False, track.duration_ms  # the update it needed never came
        return NowPlaying(playing, track.key, track.title, track.artist, None, track.duration_ms, position, now / 1000, source="feed")

    def subscribe_screen(self) -> asyncio.Queue:
        self.screens.publish(self.snapshot())  # fresh, not whatever was cached hours ago
        return self.screens.subscribe()

    # --- what the user's side sends -------------------------------------------------

    def on_push(self, push: FeedPush) -> FeedPushAck:
        now = self._clock()
        measured = now
        if push.measured_at is not None and abs(push.measured_at - now) <= CLOCK_TRUST_MS:
            measured = float(push.measured_at)
        key = track_key(push.title, push.artist) if push.title else (self.track.key if self.track else "")
        position = push.position_ms
        if position is None:  # same track: carry on from where it was; a new one starts at 0
            position = self.track.position_at(measured) if self.track and self.track.key == key else 0
        title = push.title or (self.track.title if self.track else None)
        artist = push.artist or (self.track.artist if self.track and not push.title else None)
        self.track = Track(key, title, artist, push.album, push.duration_ms, position, push.playing, push.source, measured)
        self.last_push = PushLog(at=now / 1000, playing=push.playing, title=title, artist=artist, source=push.source)
        self._awaiting = None
        self._missed = 0
        self._counters["feed:pushes"] += 1
        self.screens.publish(self.snapshot())
        self._wake.set()
        plan = self._plan(now) if self.watching else None
        return FeedPushAck(watching=self.watching, next_fetch_in_ms=int(max(0, plan.at_ms - now)) if plan else None)

    def attach_receiver(self) -> asyncio.Queue:
        if len(self.receivers) >= RECEIVER_LIMIT:
            raise TooManyReceivers()
        queue: asyncio.Queue = asyncio.Queue(maxsize=RECEIVER_QUEUE)
        self.receivers.add(queue)
        if self.watching:  # a receiver (re)connected while someone watches: catch up
            self._fetch_soon("opened", REFRESH_DEBOUNCE_MS)
        return queue

    def detach_receiver(self, queue: asyncio.Queue) -> None:
        self.receivers.discard(queue)

    def request_refresh(self, confirm_over_budget: bool) -> None:
        now = self._clock()
        if now - self._last_refresh_request_ms < REFRESH_MIN_INTERVAL_MS and self._soon is None:
            raise RefreshRefused("too_soon")
        self._prune_hour(now)
        if len(self._hour) >= self._store.settings(self.user_id).hourly_cap:
            raise RefreshRefused("hourly")
        if not confirm_over_budget and self._over_budget(now):
            raise RefreshRefused("monthly")
        self._last_refresh_request_ms = now
        self._soon_over_budget = self._soon_over_budget or confirm_over_budget
        self._fetch_soon("refresh", REFRESH_DEBOUNCE_MS)

    def settings_changed(self) -> None:
        self._blocked_until = 0.0
        self.blocked = ""
        self._wake.set()

    async def ping(self) -> bool:
        return await self._deliver(PingEvent(id=secrets.token_urlsafe(8), at=int(self._clock())), count=False)

    # --- the scheduler ----------------------------------------------------------------

    def start(self) -> None:
        self.stopped = ""
        self.task = asyncio.create_task(self._run())

    def cancel(self, reason: StopReason) -> None:
        if self.running:
            self._cancel_reason = reason
            self.task.cancel()

    async def _run(self) -> None:
        reason = StopReason.CRASHED
        try:
            await self._fetch("opened", over_budget=False)
            idle_since: float | None = None
            while True:
                now = self._clock()
                if self.screens.subscriber_count == 0:
                    idle_since = idle_since or now
                    if now - idle_since > GRACE_MS:
                        reason = StopReason.UNWATCHED
                        await self._deliver(StopEvent(at=int(now)), count=False)
                        return
                else:
                    idle_since = None
                if self._awaiting and now - self._awaiting[1] >= RESPONSE_TIMEOUT_MS:
                    self._awaiting = None
                    self._missed += 1
                plan = self._plan(now)
                if plan is not None and plan.at_ms <= now:
                    soon = self._soon is not None and plan is self._soon
                    over_budget = soon and self._soon_over_budget
                    if soon:
                        self._soon, self._soon_over_budget = None, False
                    await self._fetch(plan.reason, over_budget=over_budget)
                    continue
                wait_ms = TICK_MS if plan is None else min(TICK_MS, plan.at_ms - now)
                self._wake.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), wait_ms / 1000)
        except asyncio.CancelledError:
            reason = self._cancel_reason
            raise
        except Exception:
            log.exception("feed scheduler for user %s crashed", self.user_id)
        finally:
            self.stopped = reason.value
            self._soon = None
            if reason is StopReason.DISABLED:  # can't await here; receivers only
                self._emit_to_receivers("stop", StopEvent(at=int(self._clock())).model_dump_json())

    def _fetch_soon(self, reason: FetchReason, delay_ms: float) -> None:
        at = self._clock() + delay_ms
        if self._soon is None:  # a pending one keeps its time: that's the debounce
            self._soon = Plan(at, reason)
        self._wake.set()

    def _plan(self, now: float) -> Plan | None:
        if self._blocked_until > now:
            return Plan(self._blocked_until, "retry")
        settings = self._store.settings(self.user_id)
        planned = plan_next(now, self.track, self._last_fetch_ms, self._missed, settings.skip_check_s, settings.paused_check_s)
        if self._soon is not None and (planned is None or self._soon.at_ms <= planned.at_ms):
            return self._soon
        return planned

    def _prune_hour(self, now: float) -> None:
        while self._hour and now - self._hour[0] >= 3_600_000:
            self._hour.popleft()

    def _over_budget(self, now: float) -> bool:
        return self._store.fetches(self.user_id, month_of(now / 1000)) >= self._store.settings(self.user_id).monthly_budget

    async def _fetch(self, reason: FetchReason, over_budget: bool) -> None:
        now = self._clock()
        self._prune_hour(now)
        settings = self._store.settings(self.user_id)
        if len(self._hour) >= settings.hourly_cap:
            self.blocked, self._blocked_until = "hourly", self._hour[0] + 3_600_000
            return
        if not over_budget and self._over_budget(now):
            self.blocked, self._blocked_until = "monthly", now + 60_000  # re-checked; settings changes wake it
            return
        self.blocked = ""
        event = FetchEvent(id=secrets.token_urlsafe(8), reason=reason, at=int(now))
        self._last_fetch_ms = now  # even when undelivered: never spin
        # Awaiting from before sending: the answer can arrive before the webhook call returns.
        self._awaiting = (event.id, now)
        delivered = await self._deliver(event, count=True)
        self.last_event = EventLog(at=now / 1000, reason=reason, delivered=delivered)
        if delivered:
            self._hour.append(now)
            self._store.count_fetch(self.user_id, month_of(now / 1000))
        elif self._awaiting and self._awaiting[0] == event.id:
            self._awaiting = None  # nobody received it, so nobody can answer

    def _emit_to_receivers(self, event_type: str, body: str) -> int:
        for queue in self.receivers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait((event_type, body))
        return len(self.receivers)

    async def _deliver(self, event: FetchEvent | PingEvent | StopEvent, count: bool) -> bool:
        body = event.model_dump_json()
        delivered = self._emit_to_receivers(event.type, body) > 0
        webhook = self._store.webhook(self.user_id)
        if webhook is not None and not webhook.paused:
            result = await self._sender.deliver(webhook.url, webhook.secret, body.encode(), event.type)
            self.webhook_detail = result.detail
            if result.ok:
                self._webhook_failures = 0
                delivered = True
            else:
                self._webhook_failures += 1
                self._counters["feed:webhook_failures"] += 1
                if self._webhook_failures >= WEBHOOK_PAUSE_AFTER:
                    self._store.pause_webhook(self.user_id)
                    self.webhook_detail = f"paused after {WEBHOOK_PAUSE_AFTER} failures: {result.detail}"
        if delivered and count:
            self._counters["feed:fetches"] += 1
        return delivered

    def webhook_state(self) -> tuple[str, str]:
        webhook = self._store.webhook(self.user_id)
        if webhook is None:
            return "off", ""
        if webhook.paused:
            return "paused", self.webhook_detail
        if not self.webhook_detail:
            return "unused", ""
        return ("ok" if self._webhook_failures == 0 else "failing"), self.webhook_detail

    def hour_fetches(self) -> int:
        self._prune_hour(self._clock())
        return len(self._hour)

    @property
    def not_responding(self) -> bool:
        return self._missed > 0


def feed_status(feed: UserFeed, store: FeedStore) -> FeedStatusResponse:
    now = time.time()
    settings = store.settings(feed.user_id)
    webhook, webhook_detail = feed.webhook_state()
    return FeedStatusResponse(
        enabled=store.has_tokens(feed.user_id),
        watching=feed.watching,
        receivers=len(feed.receivers),
        webhook=webhook,
        webhook_detail=webhook_detail,
        last_event=feed.last_event,
        last_push=feed.last_push,
        not_responding=feed.not_responding,
        blocked=feed.blocked,
        month=month_of(now),
        month_fetches=store.fetches(feed.user_id, month_of(now)),
        monthly_budget=settings.monthly_budget,
        hour_fetches=feed.hour_fetches(),
        hourly_cap=settings.hourly_cap,
        stopped=feed.stopped,
    )


class FeedRegistry:
    """User id → UserFeed. A feed object lives as long as the process (it holds what was
    last pushed); its scheduler runs only while one of the user's screens is open."""

    def __init__(self, store: FeedStore, sender: WebhookSenderPort) -> None:
        self.store = store
        self._sender = sender
        self._feeds: dict[int, UserFeed] = {}
        self.counters: Counter[str] = Counter()

    def feed(self, user_id: int) -> UserFeed:
        feed = self._feeds.get(user_id)
        if feed is None:
            feed = self._feeds[user_id] = UserFeed(user_id, self.store, self._sender, self.counters)
        return feed

    def subscribe_screen(self, user_id: int) -> tuple[UserFeed, asyncio.Queue]:
        feed = self.feed(user_id)
        queue = feed.subscribe_screen()
        if not feed.running:
            feed.start()
        return feed, queue

    def resubscribe(self, user_id: int) -> None:
        """The user switched source: open screens reconnect (and get the other one)."""
        feed = self._feeds.get(user_id)
        if feed is not None:
            feed.screens.publish(RESUBSCRIBE)

    def disable(self, user_id: int) -> None:
        """The feed was turned off (last token revoked, account deleted)."""
        feed = self._feeds.get(user_id)
        if feed is not None:
            feed.cancel(StopReason.DISABLED)
            feed.screens.publish(RESUBSCRIBE)

    def forget(self, user_id: int) -> None:
        self.disable(user_id)
        self._feeds.pop(user_id, None)

    def snapshot(self) -> list[tuple[int, int]]:
        return [(uid, f.screens.subscriber_count) for uid, f in self._feeds.items() if f.running]

    async def stop_all(self) -> None:
        for feed in self._feeds.values():
            if feed.running:
                feed.cancel(StopReason.SHUTDOWN)
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await feed.task
