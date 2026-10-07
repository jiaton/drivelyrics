import re

_TAG_RE = re.compile(r"\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]")

# NetEase (and most other sources) bake credit lines into the LRC body itself, timed
# like real lyrics (typically at/near t=0) — not left in the [ar:]/[ti:]/[by:] header
# tags where they'd be easy to drop. Confirmed 2026-09-13: "I'll Make It Up To You" by
# Imagine Dragons opened with "作词 : Dan Reynolds/..." / "作曲 : ..." as its first two
# cues — Chinese songwriter-credit labels on an English song, displayed as if sung.
# Match on the label prefix, not language, since the same convention shows up in
# English-labeled sources too ("Lyrics by", "Composed by").
_METADATA_LINE_RE = re.compile(
    r"^\s*(作词|作曲|编曲|制作人|监制|混音|母带|和声|OP|SP|Lyrics by|Composed by|Producer)\s*[:：]",
    re.IGNORECASE,
)


def parse_lrc(raw: str) -> list[dict]:
    """Standard LRC: one or more [mm:ss.xx] tags per line, each tag its own cue point
    sharing that line's text. Metadata tags ([ar:], [ti:], [by:], [offset:], ...), lines
    with no timestamp, and credit lines timed into the lyric body (see above) are all
    dropped. Returns cues sorted by time, ms-resolution."""
    lines: list[dict] = []
    for raw_line in raw.splitlines():
        tags = list(_TAG_RE.finditer(raw_line))
        if not tags:
            continue
        text = _TAG_RE.sub("", raw_line).strip()
        if _METADATA_LINE_RE.match(text):
            continue
        for match in tags:
            minutes, seconds, frac = match.groups()
            ms = int(minutes) * 60_000 + int(seconds) * 1000
            if frac:
                ms += int(frac.ljust(3, "0")[:3])
            lines.append({"t": ms, "text": text})
    lines.sort(key=lambda c: c["t"])
    return lines
