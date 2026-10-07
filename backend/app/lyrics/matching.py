"""Pure scoring of lyric-provider search hits against a Spotify track. No I/O — the
service feeds it candidates from the adapter, which also makes it the one place a
"pick this candidate instead" UI can reuse to rank what it shows.

Why each signal exists (all confirmed against the live cache, 2026-10-03):
- Title: the old matcher ignored it entirely, so a same-artist song with a similar
  duration won (不完美小孩 → 剩下的盛夏, 犯贱 → 天真).
- Traditional vs simplified: Spotify keeps the original 繁体 titles (後來的我們), NetEase
  mostly lists 简体, so both sides are folded to simplified before comparing.
- Artist: compared per artist, not as one "A, B" string, and both sides folded the
  same way. Romanized names (Spotify's "Mayday" for 五月天) are avoided upstream by
  asking Spotify for zh-CN names — see spotify/adapter.py.
- Version words: covers, instrumentals, DJ/live cuts share the title and often the
  duration (拜新年 (2022) vs 拜新年 (2022) (伴奏), both 199s).
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from opencc import OpenCC

_t2s = OpenCC("t2s")

# Bracketed suffixes (feat., 电视剧《…》主题曲, Live, 眼泪未干版) and " - Live"-style tails.
# Innermost-first, applied until stable, so nested ones (片名曲 (電影《…》)) go too.
_BRACKETS_RE = re.compile(r"[(（\[【《<][^()（）\[\]【】《》<>]*[)）\]】》>]")
_DASH_TAIL_RE = re.compile(r"\s[-–—]\s.*$")
_NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)

# A candidate carrying one of these (in name or alias) while the Spotify title doesn't
# is a different recording of the same song.
_VERSION_WORDS = (
    "伴奏", "纯音乐", "instrumental", "karaoke", "off vocal", "cover", "翻自", "翻唱",
    "原唱", "dj", "remix", "live", "现场", "铃声", "片段", "加速", "降调", "0.8x", "1.2x",
)


@dataclass
class Candidate:
    song_id: str
    name: str
    artists: list[str]
    duration_ms: int | None
    album: str | None = None
    aliases: tuple[str, ...] = ()
    source: str = ""  # which provider's id song_id is


@dataclass
class ScoredCandidate:
    candidate: Candidate
    score: float
    title_score: float
    artist_score: float
    duration_score: float


def fold(text: str) -> str:
    """Width/case/script-insensitive form used for every comparison."""
    return _t2s.convert(unicodedata.normalize("NFKC", text)).lower().strip()


def _strip_brackets(text: str) -> str:
    while True:
        stripped = _BRACKETS_RE.sub("", text)
        if stripped == text:
            return stripped
        text = stripped


def core_title(title: str) -> str:
    stripped = _DASH_TAIL_RE.sub("", _strip_brackets(fold(title)))
    return _NON_WORD_RE.sub("", stripped) or _NON_WORD_RE.sub("", fold(title))


def query_title(title: str) -> str:
    """Title as a search query: decorations dropped, spacing and script kept."""
    stripped = _DASH_TAIL_RE.sub("", _strip_brackets(unicodedata.normalize("NFKC", title))).strip()
    return stripped or title


_ARTIST_SPLIT_RE = re.compile(r"\s*(?:,|&|、|\bfeat\.?|\bft\.?)\s*", re.IGNORECASE)


def split_artists(artist: str) -> list[str]:
    """Spotify's adapter joins artists with ", "; LRCLIB puts them all in one string
    joined with ", ", " & " or "feat."."""
    return [a for a in (part.strip() for part in _ARTIST_SPLIT_RE.split(artist)) if a]


_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def has_cjk(text: str) -> bool:
    return _CJK_RE.search(text) is not None


def _title_score(spotify_title: str, candidate: Candidate) -> float:
    target = core_title(spotify_title)
    best = 0.0
    for name in (candidate.name, *candidate.aliases):
        other = core_title(name)
        if not other:
            continue
        if other == target:
            return 1.0
        if target in other or other in target:
            best = max(best, 0.8)
        else:
            best = max(best, 0.6 * SequenceMatcher(None, target, other).ratio())
    return best


def _artist_score(spotify_artists: list[str], candidate: Candidate) -> float:
    if not spotify_artists:
        return 0.0
    theirs = [fold(a) for a in candidate.artists]
    matched = 0
    for ours in (fold(a) for a in spotify_artists):
        # Containment covers "五月天" vs "五月天 (Mayday)" style annotations.
        if any(ours == t or (len(ours) > 1 and (ours in t or t in ours)) for t in theirs):
            matched += 1
    return matched / len(spotify_artists)


def _duration_score(spotify_ms: int | None, candidate_ms: int | None) -> float:
    if spotify_ms is None or not candidate_ms:
        return 0.5
    diff_s = abs(spotify_ms - candidate_ms) / 1000
    if diff_s <= 2:
        return 1.0
    return max(0.0, 1 - (diff_s - 2) / 18)  # 0 at 20s off


def _has_word(text: str, word: str) -> bool:
    if word.isascii():  # "live" must not fire on "Alive"
        return re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", text) is not None
    return word in text


def _version_penalty(spotify_title: str, candidate: Candidate) -> float:
    ours = fold(spotify_title)
    theirs = fold(" ".join((candidate.name, *candidate.aliases)))
    for word in _VERSION_WORDS:
        if _has_word(theirs, word) and not _has_word(ours, word):
            return 1.5
    return 0.0


def score(title: str, artist: str, duration_ms: int | None, candidate: Candidate) -> ScoredCandidate:
    title_s = _title_score(title, candidate)
    artist_s = _artist_score(split_artists(artist), candidate)
    duration_s = _duration_score(duration_ms, candidate.duration_ms)
    total = 3.0 * title_s + 2.0 * artist_s + 1.5 * duration_s - _version_penalty(title, candidate)
    return ScoredCandidate(candidate, total, title_s, artist_s, duration_s)


def rank(title: str, artist: str, duration_ms: int | None, candidates: list[Candidate]) -> list[ScoredCandidate]:
    """Best first; duplicates (same provider id from two searches) collapsed."""
    seen: dict[tuple[str, str], ScoredCandidate] = {}
    for c in candidates:
        if (c.source, c.song_id) not in seen:
            seen[(c.source, c.song_id)] = score(title, artist, duration_ms, c)
    return sorted(seen.values(), key=lambda s: s.score, reverse=True)


def is_confident(best: ScoredCandidate) -> bool:
    """Good enough that a second, broader search isn't worth it."""
    return best.title_score >= 0.8 and best.artist_score > 0 and best.duration_score >= 0.5


def is_acceptable(best: ScoredCandidate) -> bool:
    """Good enough to show. Showing nothing beats confidently showing the wrong song:
    some catalogs (周杰伦, licensed to QQ Music) aren't on NetEase at all, and then every
    hit is a cover or a clipped re-upload (稻香 → 稻香(治愈版), 120s of a 223s song).
    - same title, a matching artist, and a duration that isn't wildly off; or
    - same title and near-exact duration without an artist match — a re-upload of
      the same audio under another uploader's name, whose timing still lines up."""
    if best.score < 3.0 or best.title_score < 0.8:
        return False
    if best.artist_score > 0:
        return best.duration_score > 0
    return best.title_score == 1.0 and best.duration_score == 1.0
