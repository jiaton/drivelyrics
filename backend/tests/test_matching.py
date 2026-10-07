"""Replays real NetEase search responses (tests/fixtures/netease_search.json, recorded
2026-10-03) for songs the old matcher got wrong in the live cache, through the real
LyricsService.match_in — only the provider's HTTP boundary is faked."""

import json
from pathlib import Path

import pytest

from app.lyrics.matching import Candidate, core_title, fold, is_acceptable, query_title, rank
from app.lyrics.service import LyricsService, TrackInfo

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "netease_search.json").read_text())


class RecordedSource:
    name = "netease"

    async def search(self, keywords):
        return [
            Candidate(
                song_id=str(s["id"]),
                name=s["name"],
                artists=[a["name"] for a in s["artists"]],
                duration_ms=s["duration"],
                album=s["album"]["name"],
                aliases=tuple(s["alias"]),
                source="netease",
            )
            for s in FIXTURES[keywords]
        ]

    async def fetch_raw_lyric(self, song_id):
        raise AssertionError("not used")


# (Spotify title, Spotify artists as returned with Accept-Language: zh-CN, duration,
#  expected NetEase title after folding or None to only check it's no cover/instrumental,
#  expected first artist or None). NO_MATCH: the original isn't on NetEase.
NO_MATCH = object()

CASES = [
    ("後來的我們", "五月天", 346_000, "后来的我们", "五月天"),  # was 第三人称 / MAYDAY
    ("兄弟", "五月天", 248_000, "兄弟", "五月天"),  # was 龙井说唱's 兄弟
    ("人生有限公司", "五月天", 218_000, "人生有限公司", "五月天"),  # was Invicible
    # was 稻香(深情版) / Lucky小爱; only covers and a 120s 治愈版 exist on NetEase
    ("稻香", "周杰伦", 223_000, NO_MATCH, None),
    # was 剩下的盛夏; the TFBOYS original isn't listed, a same-length re-upload is
    ("不完美小孩", "TFBOYS", 260_000, "不完美小孩", None),
    ("犯贱", "徐良, 阿悄", 222_000, "犯贱", "徐良"),  # was 天真
    ("年少有為", "李荣浩", 279_000, "年少有为", "李荣浩"),
    ("考試週 (feat. 喬瑟夫 & 宮敬婷)", "這群人, 喬瑟夫, 宮敬婷", 512_000, None, "这群人"),
    ("拜新年", "凤凰传奇", 199_000, None, "凤凰传奇"),  # (伴奏) has the same duration
    ("不谓侠", "萧忆情", 267_000, "不谓侠", None),  # was a "cover萧忆情"
    ("时间有泪 - Live", "张碧晨", 328_000, None, "张碧晨"),
    ("Counting Stars", "OneRepublic", 257_000, "counting stars", "OneRepublic"),
]


@pytest.mark.parametrize("title,artist,duration_ms,want_title,want_artist", CASES, ids=[case[0] for case in CASES])
async def test_real_cases_pick_the_right_recording(title, artist, duration_ms, want_title, want_artist):
    source = RecordedSource()
    match = await LyricsService([source]).match_in(source, TrackInfo("id", title, artist, duration_ms))

    if want_title is NO_MATCH:
        assert match is None, match
        return
    assert match is not None
    got = match.candidate
    if want_title is not None:
        assert core_title(got.name) == core_title(want_title), got
    if want_artist is not None:
        assert fold(want_artist) in [fold(a) for a in got.artists], got
    for word in ("伴奏", "cover", "翻自", "翻唱", "dj"):
        assert word not in fold(got.name), got


def c(song_id, name, artists, seconds, aliases=()):
    return Candidate(song_id, name, artists, seconds * 1000, aliases=tuple(aliases))


def test_title_beats_same_artist_same_duration():
    ranked = rank("一代天骄", "凤凰传奇", 283_000, [
        c("1", "最后的讨伐", ["凤凰传奇"], 283),
        c("2", "一代天骄", ["凤凰传奇"], 283),
    ])
    assert ranked[0].candidate.song_id == "2"


def test_instrumental_loses_to_vocal_at_equal_duration():
    ranked = rank("拜新年 (2022)", "凤凰传奇", 199_000, [
        c("1", "拜新年 (2022) (伴奏)", ["凤凰传奇"], 199),
        c("2", "拜新年 (2022)", ["凤凰传奇"], 199),
    ])
    assert ranked[0].candidate.song_id == "2"


def test_live_is_not_penalized_when_spotify_title_is_live_too():
    ranked = rank("时间有泪 - Live", "张碧晨", 328_000, [
        c("1", "时间有泪", ["张碧晨"], 270),
        c("2", "时间有泪 (Live)", ["张碧晨"], 328),
    ])
    assert ranked[0].candidate.song_id == "2"


def test_live_word_needs_a_word_boundary():
    ranked = rank("Alive", "Sia", 263_000, [c("1", "Alive", ["Sia"], 263)])
    assert ranked[0].score > 6


def test_traditional_and_simplified_fold_together():
    assert fold("後來的我們") == fold("后来的我们")
    assert core_title("考試週 (feat. 喬瑟夫 & 宮敬婷)") == core_title("考试周 (feat. 乔瑟夫 & 宫敬婷)")


def test_clipped_reupload_by_the_right_artist_is_rejected():
    best = rank("稻香", "周杰伦", 223_000, [c("1", "稻香(治愈版)", ["周杰伦."], 120)])[0]
    assert not is_acceptable(best)


def test_query_title_keeps_spaces_and_script():
    assert query_title("Counting Stars") == "Counting Stars"
    assert query_title("後來的我們 (電影《後來的我們》片名曲)") == "後來的我們"
    assert query_title("时间有泪 - Live") == "时间有泪"
