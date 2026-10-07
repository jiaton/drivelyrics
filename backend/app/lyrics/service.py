import asyncio
import logging
from collections import Counter
import time
import weakref
from dataclasses import dataclass

from sqlmodel import Session, select

from app.lyrics.lrc_parser import parse_lrc
from app.lyrics.matching import ScoredCandidate, has_cjk, is_acceptable, is_confident, query_title, rank, split_artists
from app.lyrics.models import LyricsText, TrackMatch, UserTrackSource
from app.lyrics.ports import LyricsSourcePort

# Bump when matching changes in a way that should re-match already-cached tracks. Rows
# written by an older matcher are treated as misses (and overwritten), so a fix reaches
# tracks that were matched wrong before it. Manual picks are never re-matched.
# 1 = artist filter + closest duration (title ignored); 2 = matching.py scoring;
# 3 = keyed by Spotify track id, NetEase + LRCLIB.
MATCH_VERSION = 3

MAX_CANDIDATES = 12

log = logging.getLogger(__name__)


class UnknownSource(Exception):
    pass


class NoSyncedLyrics(Exception):
    pass


@dataclass
class TrackInfo:
    track_id: str
    title: str
    artist: str
    duration_ms: int | None


@dataclass
class LyricsResult:
    lines: list[dict]
    translation_lines: list[dict]
    source: str  # "" = no lyrics found
    song_id: str
    manual: bool


def source_order(track: TrackInfo, preference: str, show_translation: bool) -> list[str]:
    """Which provider to try first for this reader. NetEase is the one with translations
    (and the strongest Chinese catalog); LRCLIB the stronger one for English.
    "auto": NetEase first when the reader shows translations (so English songs come with
    their Chinese translation) or the track is CJK; LRCLIB first otherwise."""
    if preference == "netease":
        return ["netease", "lrclib"]
    if preference == "lrclib":
        return ["lrclib", "netease"]
    if show_translation or has_cjk(track.title + track.artist):
        return ["netease", "lrclib"]
    return ["lrclib", "netease"]


def reader_order(db: Session, user_id: int, track: TrackInfo, preference: str, show_translation: bool) -> list[str]:
    """source_order, unless this reader pinned a source for this very track."""
    order = source_order(track, preference, show_translation)
    pin = db.get(UserTrackSource, (user_id, track.track_id))
    if pin is not None and pin.source in order:
        order = [pin.source] + [s for s in order if s != pin.source]
    return order


class LyricsService:
    """Shared by every user: lyrics for a Spotify track are the same whoever plays it,
    so one lookup (or one person's manual fix) serves everyone."""

    def __init__(self, sources: list[LyricsSourcePort]) -> None:
        self._sources = {s.name: s for s in sources}
        # One lookup per track at a time: two screens opening the same new song wait
        # for the first lookup instead of each searching the providers.
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()
        # Since process start (in memory, reset by a restart): what lookups cost and
        # what readers ended up seeing. Read by the admin stats page.
        self.counters: Counter[str] = Counter()
        self.counting_since = time.time()

    @property
    def source_names(self) -> list[str]:
        return list(self._sources)

    def _ordered(self, order: list[str]) -> list[LyricsSourcePort]:
        return [self._sources[n] for n in order if n in self._sources]

    async def _search(self, source: LyricsSourcePort, track: TrackInfo, broad: bool) -> list[ScoredCandidate]:
        """"title artist" first; then, if broad or nothing convincing came back, the bare
        title as well (a differently written artist in the query can push the real song
        out of the provider's top hits: 兄弟 + "Mayday" returned only other artists')."""
        hits = await source.search(f"{track.title} {' '.join(split_artists(track.artist))}")
        ranked = rank(track.title, track.artist, track.duration_ms, hits)
        if broad or not ranked or not is_confident(ranked[0]):
            hits += await source.search(query_title(track.title))
            ranked = rank(track.title, track.artist, track.duration_ms, hits)
        return ranked

    async def match_in(self, source: LyricsSourcePort, track: TrackInfo) -> ScoredCandidate | None:
        ranked = await self._search(source, track, broad=False)
        return ranked[0] if ranked and is_acceptable(ranked[0]) else None

    async def candidates(self, track: TrackInfo) -> list[ScoredCandidate]:
        """Everything plausible from every source, best first, for the manual picker."""
        results = await asyncio.gather(
            *(self._search(s, track, broad=True) for s in self._sources.values()), return_exceptions=True
        )
        merged = [c for r in results if isinstance(r, list) for c in r]
        merged.sort(key=lambda c: c.score, reverse=True)
        return merged[:MAX_CANDIDATES]

    async def _text(self, db: Session, source: str, song_id: str) -> LyricsText:
        row = db.get(LyricsText, (source, song_id))
        if row is not None:
            return row
        raw = await self._sources[source].fetch_raw_lyric(song_id)
        row = LyricsText(source=source, song_id=song_id, lrc_text=raw.lrc or "", tlyric_text=raw.tlyric or "", fetched_at=time.time())
        db.add(row)
        db.commit()
        return row

    def _result(self, row: TrackMatch | None, text: LyricsText | None) -> LyricsResult:
        return LyricsResult(
            lines=parse_lrc(text.lrc_text) if text else [],
            translation_lines=parse_lrc(text.tlyric_text) if text else [],
            source=row.source if row and text else "",
            song_id=row.source_song_id if row and text else "",
            manual=bool(row and text and row.manual),
        )

    def _save(self, db: Session, track: TrackInfo, source: str, song_id: str, manual: bool, user_id: int | None) -> TrackMatch:
        row = db.get(TrackMatch, (track.track_id, source)) or TrackMatch(
            spotify_track_id=track.track_id, source=source, title="", artist="", match_version=0, updated_at=0
        )
        row.title, row.artist, row.source_song_id = track.title, track.artist, song_id
        row.match_version, row.manual, row.chosen_by = MATCH_VERSION, manual, user_id
        row.updated_at = time.time()
        db.add(row)
        db.commit()
        return row

    async def _lyrics_of(self, db: Session, row: TrackMatch) -> LyricsText | None:
        """The row's lyrics if it points at a song with synced lines."""
        if not row.source_song_id or row.source not in self._sources:
            return None
        text = await self._text(db, row.source, row.source_song_id)
        return text if parse_lrc(text.lrc_text) else None

    async def get_lyrics(self, db: Session, track: TrackInfo, order: list[str]) -> LyricsResult:
        """The first source in the reader's order whose row has synced lyrics. Within a
        source, a manual row (someone's correction) simply *is* that source's answer; a
        manual row with no song ("this source has the wrong song") is skipped and never
        re-searched. A source is only searched when a reader reaches it, and the result
        is cached for everyone. A provider error isn't cached: the next play retries."""
        lock = self._locks.get(track.track_id)
        if lock is None:
            lock = self._locks[track.track_id] = asyncio.Lock()
        async with lock:
            rows = {row.source: row for row in db.exec(select(TrackMatch).where(TrackMatch.spotify_track_id == track.track_id))}
            searched = False
            for source in self._ordered(order):
                row = rows.get(source.name)
                if row is None or (not row.manual and row.match_version < MATCH_VERSION):
                    searched = True
                    try:
                        best = await self.match_in(source, track)
                        song_id = best.candidate.song_id if best else ""
                        if song_id:
                            await self._text(db, source.name, song_id)  # fetch now: errors land here
                    except Exception:
                        log.exception("lyrics lookup via %s failed", source.name)
                        self.counters[f"error:{source.name}"] += 1
                        continue
                    row = self._save(db, track, source.name, song_id, manual=False, user_id=None)
                if text := await self._lyrics_of(db, row):
                    self._count(searched, row.source)
                    return self._result(row, text)
            self._count(searched, "")
            return self._result(None, None)

    def _count(self, searched: bool, shown_source: str) -> None:
        self.counters["searched" if searched else "cached"] += 1
        self.counters[f"shown:{shown_source or 'none'}"] += 1

    async def choose(
        self, db: Session, track: TrackInfo, source: str, song_id: str, user_id: int, wrong_source: str | None = None
    ) -> LyricsResult:
        """A reader picked (source, song_id) as this track's lyrics.
        - For everyone: it becomes `source`'s answer for this track (a correction within
          that source; readers preferring the other source are unaffected).
        - For this reader only: `source` is pinned for this track, so they see it even if
          they'd normally get the other source first.
        - wrong_source: the reader said the lyrics they were shown (from that other
          source) were the wrong song. That source is then skipped for this track, for
          everyone — without this, switching source is just a personal preference.
        Validated by fetching the lyrics, so a pick can't point at nothing."""
        if source not in self._sources or (wrong_source is not None and wrong_source not in self._sources):
            raise UnknownSource(source)
        text = await self._text(db, source, song_id)
        if not parse_lrc(text.lrc_text):
            raise NoSyncedLyrics(f"{source}:{song_id}")
        row = db.get(TrackMatch, (track.track_id, source))
        if row is None or row.manual or row.source_song_id != song_id:
            # A different answer than this source's automatic match: a correction.
            # (Re-picking the automatic match itself, e.g. to switch source, changes
            # nothing for anyone else and isn't one.)
            row = self._save(db, track, source, song_id, manual=True, user_id=user_id)
        if wrong_source and wrong_source != source:
            self._save(db, track, wrong_source, "", manual=True, user_id=user_id)
        pin = db.get(UserTrackSource, (user_id, track.track_id)) or UserTrackSource(
            user_id=user_id, spotify_track_id=track.track_id, source=source, updated_at=0
        )
        pin.source, pin.updated_at = source, time.time()
        db.add(pin)
        db.commit()
        self.counters["picks"] += 1
        return self._result(row, text)


def forget_user(db: Session, user_id: int) -> None:
    """Account deletion: drop the user's own source pins; keep their corrections (they
    help everyone) but no longer say who made them."""
    for pin in db.exec(select(UserTrackSource).where(UserTrackSource.user_id == user_id)):
        db.delete(pin)
    for row in db.exec(select(TrackMatch).where(TrackMatch.chosen_by == user_id)):
        row.chosen_by = None
        db.add(row)
    db.commit()
