"""Train the Cantonese word-usage score (app/lyrics/cantonese_model.py) and write
app/lyrics/cantonese_weights.py. Pure Python, no extra dependencies:

    poetry run python scripts/cantonese/train.py CORPUS.jsonl

CORPUS.jsonl: one song per line, {"lrc": "...", "roma": bool, "artists": [...]}, as
written by collect.py — `roma` (the provider romanizes the lyrics) is the label.
Prints an artist-grouped cross-validation first: no test song's artist is seen in
training, so the numbers reflect artists the score has never met."""

import json
import math
import re
import sys
import time
import zlib
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.lyrics.cantonese_model import features  # noqa: E402

K = 80  # characters/pairs kept
MIN_DF = 0.03  # used by at least this share of songs…
MIN_ARTISTS = 8  # …by at least this many artists, so one song's words can't count
EXCLUDE = {"歌曲", "音乐"}  # from credit lines ("音乐制作…"), not lyrics
THRESHOLD = 0.8  # chosen for few Mandarin songs taken for Cantonese
FOLDS = 5
_KANA_HANGUL = re.compile(r"[぀-ヿ가-힯]")
OUT = Path(__file__).resolve().parents[2] / "app" / "lyrics" / "cantonese_weights.py"


def load(path: str) -> list[tuple[set[str], bool, str]]:
    docs = []
    for line in open(path, encoding="utf-8"):
        song = json.loads(line)
        if _KANA_HANGUL.search(song["lrc"]):
            continue  # Japanese/Korean: romanized, but not Cantonese
        grams = features(song["lrc"])
        if grams:
            docs.append((grams, bool(song["roma"]), (song.get("artists") or ["?"])[0]))
    return docs


def select(docs: list[tuple[set[str], bool, str]]) -> list[str]:
    n = Counter(y for _, y, _ in docs)
    df: dict[bool, Counter] = {True: Counter(), False: Counter()}
    artists: dict[str, set[str]] = defaultdict(set)
    for grams, y, artist in docs:
        df[y].update(grams)
        for g in grams:
            artists[g].add(artist)
    scored = []
    for g in set(df[True]) | set(df[False]):
        total = df[True][g] + df[False][g]
        if g in EXCLUDE or total < MIN_DF * len(docs) or len(artists[g]) < MIN_ARTISTS:
            continue
        p = (df[True][g] + 1) / (n[True] + 2)
        q = (df[False][g] + 1) / (n[False] + 2)
        gap = abs(math.log(p / (1 - p)) - math.log(q / (1 - q)))
        scored.append((gap * min(1.0, total / (0.1 * len(docs))) ** 0.5, g))  # favour common words
    return [g for _, g in sorted(scored, reverse=True)[:K]]


def fit(docs: list[tuple[set[str], bool, str]], feats: list[str], steps: int = 3000) -> tuple[float, dict[str, float]]:
    """Class-balanced logistic regression with L2 (C = 1), full-batch Adam."""
    index = {g: i for i, g in enumerate(feats)}
    rows = [([index[g] for g in grams if g in index], y) for grams, y, _ in docs]
    n = len(rows)
    pos = sum(y for _, y in rows)
    class_w = {True: n / (2 * pos), False: n / (2 * (n - pos))}
    w = [0.0] * (len(feats) + 1)  # last = bias
    m = [0.0] * len(w)
    v = [0.0] * len(w)
    for step in range(1, steps + 1):
        grad = [wi for wi in w[:-1]] + [0.0]  # L2 on weights, not on the bias
        for active, y in rows:
            z = w[-1] + sum(w[i] for i in active)
            err = (1 / (1 + math.exp(-z)) - y) * class_w[y]
            for i in active:
                grad[i] += err
            grad[-1] += err
        for i, g in enumerate(grad):
            g /= n
            m[i] = 0.9 * m[i] + 0.1 * g
            v[i] = 0.999 * v[i] + 0.001 * g * g
            w[i] -= 0.05 * (m[i] / (1 - 0.9**step)) / (math.sqrt(v[i] / (1 - 0.999**step)) + 1e-8)
    return w[-1], {g: w[i] for i, g in enumerate(feats)}


def probability(grams: set[str], bias: float, weights: dict[str, float]) -> float:
    return 1 / (1 + math.exp(-(bias + sum(wt for g, wt in weights.items() if g in grams))))


def cross_validate(docs: list[tuple[set[str], bool, str]]) -> str:
    fold = lambda artist: zlib.crc32(artist.encode()) % FOLDS  # noqa: E731
    scores: list[tuple[float, bool]] = []
    for k in range(FOLDS):
        train = [d for d in docs if fold(d[2]) != k]
        bias, weights = fit(train, select(train), steps=1500)
        scores += [(probability(g, bias, weights), y) for g, y, a in docs if fold(a) == k]
    lines = []
    for th in (0.5, 0.7, THRESHOLD, 0.9):
        mandarin = [p for p, y in scores if not y]
        cantonese = [p for p, y in scores if y]
        fp = sum(p >= th for p in mandarin) / len(mandarin)
        found = sum(p >= th for p in cantonese) / len(cantonese)
        lines.append(f"threshold {th}: Mandarin taken for Cantonese {fp:.1%}, Cantonese found {found:.1%}")
    return "\n".join(lines)


def main() -> None:
    docs = load(sys.argv[1])
    print(f"{len(docs)} songs, {sum(y for _, y, _ in docs)} Cantonese, {len({a for *_, a in docs})} artists")
    report = cross_validate(docs)
    print(report)
    feats = select(docs)
    bias, weights = fit(docs, feats)
    ordered = sorted(weights.items(), key=lambda kv: -kv[1])
    body = "\n".join(f"    {g!r}: {wt:.3f}," for g, wt in ordered)
    comment = "\n".join(f"# {line}" for line in report.splitlines())
    OUT.write_text(
        f'"""Generated by scripts/cantonese/train.py on {time.strftime("%Y-%m-%d")} from {len(docs)} songs '
        f'({sum(y for _, y, _ in docs)} Cantonese) — do not edit by hand."""\n\n'
        f"# Artist-grouped cross-validation:\n{comment}\n\n"
        f"BIAS = {bias:.3f}\nTHRESHOLD = {THRESHOLD}\nWEIGHTS: dict[str, float] = {{\n{body}\n}}\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
