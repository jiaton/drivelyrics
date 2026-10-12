"""Was this lyrics text written to be sung in Cantonese? A word-usage score. Pure, no I/O.

Most Cantopop is written in standard written Chinese, not colloquial Cantonese (嘅/咗
are rare), and NetEase serves everything in 简体, so neither colloquial characters nor
glyph forms tell the languages apart (measured 2026-10-11). Word choice does:
Cantonese lyricists favour literary words that sit well in Cantonese tones (仍 亦 似
令 未 共 便 谁人 只得 几多) and avoid Mandarin's colloquial function words (们 不是
因为 可是 时间 我们 为什么). The weights in cantonese_weights.py are a logistic
regression over which of ~80 such characters/pairs a song uses at all, trained by
scripts/cantonese/train.py on NetEase lyrics labelled by whether NetEase romanizes them.
Cross-validated by artist: at THRESHOLD, ~2–3% of Mandarin songs are taken for
Cantonese (several of those were mislabelled) and ~80% of Cantonese songs are found;
on LRCLIB's 繁體 copies of other songs, 0 of 33 Mandarin and 31 of 42 Cantonese."""

import math
import re

from opencc import OpenCC

from app.lyrics.cantonese_weights import BIAS, THRESHOLD, WEIGHTS

_t2s = OpenCC("t2s")
_TAG = re.compile(r"\[[^\]]*\]")
_HAN_RUN = re.compile(r"[一-鿿]+")
_CREDIT = re.compile(r"[:：]")
MIN_HAN = 30  # shorter texts say too little to judge


def features(lrc_text: str) -> set[str] | None:
    """Every Han character and adjacent pair the lyrics use (in 简体, repeated lines
    once, short credit lines like "作词：…" skipped); None when there's too little text."""
    seen: set[str] = set()
    runs: list[str] = []
    for raw in lrc_text.splitlines():
        line = _TAG.sub("", raw).strip()
        if not line or (_CREDIT.search(line) and len(line) < 30):
            continue
        line = _t2s.convert(line)
        if line in seen:
            continue
        seen.add(line)
        runs += _HAN_RUN.findall(line)
    if sum(map(len, runs)) < MIN_HAN:
        return None
    grams: set[str] = set()
    for run in runs:
        grams.update(run)
        grams.update(run[i : i + 2] for i in range(len(run) - 1))
    return grams


def probability(grams: set[str], weights: dict[str, float] = WEIGHTS, bias: float = BIAS) -> float:
    z = bias + sum(w for gram, w in weights.items() if gram in grams)
    return 1 / (1 + math.exp(-z))


def written_for_cantonese(lrc_text: str) -> bool:
    grams = features(lrc_text)
    return grams is not None and probability(grams) >= THRESHOLD
