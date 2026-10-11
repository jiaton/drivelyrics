"""Is a track sung in Cantonese? The guess itself is jyutping.looks_cantonese; this adds
what it needs from storage: a reader's mark, and whether a provider romanized the lyrics."""

import logging
import time

from sqlmodel import Session, select

from app.lyrics.jyutping import looks_cantonese
from app.lyrics.models import LyricsText, TrackCantonese, TrackMatch
from app.lyrics.ports import LyricsSourcePort

log = logging.getLogger(__name__)


async def _romanized(db: Session, sources: dict[str, LyricsSourcePort], text: LyricsText) -> bool:
    """text.romanized, read from the provider once for lyrics cached before it was
    recorded. An error counts as "no" for now and isn't saved."""
    if text.romanized is not None:
        return text.romanized
    if text.source not in sources:
        return False
    try:
        raw = await sources[text.source].fetch_raw_lyric(text.song_id)
    except Exception:
        log.exception("re-reading %s:%s for its romanization failed", text.source, text.song_id)
        return False
    text.romanized = raw.romanized
    db.add(text)
    db.commit()
    return raw.romanized


async def is_cantonese(db: Session, sources: dict[str, LyricsSourcePort], track_id: str, text: LyricsText) -> bool:
    """A reader's mark on the track wins; otherwise the guess, using a romanization from
    any source's cached lyrics for the track — LRCLIB lyrics of a Cantonese song still
    count when NetEase's copy was romanized. track_id "" = a song looked up by search,
    not a Spotify track: the guess from these lyrics alone."""
    mark = db.get(TrackCantonese, track_id) if track_id else None
    if mark is not None:
        return mark.cantonese
    if not looks_cantonese(text.lrc_text, provider_romanized=True):
        return False  # no Han characters, or Japanese/Korean: nothing to look up
    if looks_cantonese(text.lrc_text, provider_romanized=False):
        return True
    if await _romanized(db, sources, text):
        return True
    if not track_id:
        return False
    for match in db.exec(select(TrackMatch).where(TrackMatch.spotify_track_id == track_id)):
        other = db.get(LyricsText, (match.source, match.source_song_id)) if match.source_song_id else None
        if other is not None and other is not text and other.romanized:
            return True
    return False


def mark_cantonese(db: Session, track_id: str, cantonese: bool, user_id: int) -> None:
    """A reader says whether this track is sung in Cantonese — for everyone."""
    mark = db.get(TrackCantonese, track_id) or TrackCantonese(spotify_track_id=track_id, cantonese=cantonese, updated_at=0)
    mark.cantonese, mark.set_by, mark.updated_at = cantonese, user_id, time.time()
    db.add(mark)
    db.commit()
