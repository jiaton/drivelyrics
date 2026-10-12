"""Cantonese: is a song sung in it, and its lyrics in Jyutping (粵拼). Pure, no I/O.

Jyutping is generated here, not taken from a provider: NetEase's own romanization for
Cantonese songs (`romalrc`) is a crowd-written, Mandarin-style spelling with no tones —
富士山下 has "lan lou yv pin ci sv fa" where Jyutping is "laan4 lou6 jyu5 pin1 ci5 syut3
faa1". ToJyutping (CanCLID, BSD-2) segments words, so most 多音字 come out right; it
reads 繁體 better than 简体 (风褛 → leoi5, 風褸 → lau1), hence the s2hk conversion first.

Whether a song is Cantonese at all is cantonese.is_cantonese; the text-only checks it
uses are here and in cantonese_model.py."""

import re

import ToJyutping
from opencc import OpenCC

_s2hk = OpenCC("s2hk")
_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_KANA_HANGUL = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\u1100-\u11ff\uac00-\ud7af]")
# Written only in colloquial Cantonese. Not 唔 or 乜: Mandarin lyrics use those as
# interjections. Two hits needed, so one stray character doesn't decide.
_CANTONESE_ONLY = set("嘅咗冇佢喺啲嗰哋㗎嚟嘢咩噉啱嘥攰瞓諗揾搵")
_MIN_CANTONESE_CHARS = 2


def chinese_lyrics(lrc_text: str) -> bool:
    """Han characters and no kana/hangul: Chinese, so possibly Cantonese. (Japanese and
    Korean lyrics are romanized by NetEase too.)"""
    return bool(_HAN.search(lrc_text)) and not _KANA_HANGUL.search(lrc_text)


def colloquial_cantonese(lrc_text: str) -> bool:
    return sum(ch in _CANTONESE_ONLY for ch in lrc_text) >= _MIN_CANTONESE_CHARS


def line_jyutping(text: str) -> str:
    """"攔路雨偏似雪花" → "laan4 lou6 jyu5 pin1 ci5 syut3 faa1". Latin words in the line
    are kept as they are; punctuation is dropped. "" when the line has no Han characters."""
    if not _HAN.search(text):
        return ""
    out: list[str] = []
    word = ""
    for ch, jyutping in ToJyutping.get_jyutping_list(_s2hk.convert(text)):
        if jyutping:
            if word:
                out.append(word)
                word = ""
            out.append(jyutping)
        elif ch.isalnum():
            word += ch
        elif word:
            out.append(word)
            word = ""
    if word:
        out.append(word)
    return " ".join(out)
