"""Which lyrics source a reader sees first. Pure apart from reading the reader's pin."""

from sqlmodel import Session

from app.lyrics.matching import has_cjk
from app.lyrics.models import UserTrackSource
from app.lyrics.service import TrackInfo


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
