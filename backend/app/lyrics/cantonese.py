"""Is a track sung in Cantonese? Readers' votes first; otherwise a guess from the lyrics.

The guess, strongest signal first: colloquial Cantonese characters (rare: most
Cantopop is written in standard Chinese); the word-usage score (cantonese_model.py,
works on any source's text); NetEase shipping a romanization for Chinese lyrics
(every Cantonese song checked had one, no Mandarin or Hokkien song did — but some
Cantonese songs lack one, which the score catches), also from another source's cached
copy of the same track."""

import logging
import time

from sqlmodel import Session, func, select

from app.lyrics.cantonese_model import written_for_cantonese
from app.lyrics.jyutping import chinese_lyrics, colloquial_cantonese
from app.lyrics.models import CantoneseVote, LyricsText, TrackMatch
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


def _voted(db: Session, track_id: str, user_id: int | None) -> bool | None:
    """The reader's own vote; else the majority's; None on a tie or no votes."""
    if user_id is not None and (own := db.get(CantoneseVote, (user_id, track_id))) is not None:
        return own.cantonese
    counts = dict(
        db.exec(
            select(CantoneseVote.cantonese, func.count())
            .where(CantoneseVote.spotify_track_id == track_id)
            .group_by(CantoneseVote.cantonese)
        ).all()
    )
    yes, no = counts.get(True, 0), counts.get(False, 0)
    return None if yes == no else yes > no


async def is_cantonese(
    db: Session, sources: dict[str, LyricsSourcePort], track_id: str, text: LyricsText, user_id: int | None = None
) -> bool:
    """track_id "" = a song looked up by search, not a Spotify track: no votes, and only
    these lyrics to go on."""
    if track_id and (voted := _voted(db, track_id, user_id)) is not None:
        return voted
    if not chinese_lyrics(text.lrc_text):
        return False
    if colloquial_cantonese(text.lrc_text) or written_for_cantonese(text.lrc_text):
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


def vote_cantonese(db: Session, track_id: str, cantonese: bool, user_id: int) -> None:
    vote = db.get(CantoneseVote, (user_id, track_id)) or CantoneseVote(
        user_id=user_id, spotify_track_id=track_id, cantonese=cantonese, updated_at=0
    )
    vote.cantonese, vote.updated_at = cantonese, time.time()
    db.add(vote)
    db.commit()
