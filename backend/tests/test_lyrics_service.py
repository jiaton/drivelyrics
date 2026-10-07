import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.auth.models import User
from app.lyrics.matching import Candidate
from app.lyrics.models import TrackMatch
from app.lyrics.ports import RawLyric
from app.lyrics.service import MATCH_VERSION, LyricsService, NoSyncedLyrics, TrackInfo, reader_order, source_order


class FakeSource:
    """Fake adapter — tests mock the port boundary, never LyricsService's internals."""

    def __init__(self, name, hits=None, lrc="[00:01.00]hello", tlyric=None, fail=False):
        self.name = name
        self.hits = hits if hits is not None else [Candidate("s1", "Song", ["Artist"], 200_000, source=name)]
        self.lrc, self.tlyric, self.fail = lrc, tlyric, fail
        self.search_calls: list[str] = []
        self.fetch_calls: list[str] = []

    async def search(self, keywords):
        self.search_calls.append(keywords)
        if self.fail:
            raise RuntimeError("provider down")
        return list(self.hits)

    async def fetch_raw_lyric(self, song_id):
        self.fetch_calls.append(song_id)
        return RawLyric(lrc=self.lrc, tlyric=self.tlyric)


SONG = TrackInfo("track-1", "Song", "Artist", 200_000)
LRCLIB_FIRST = ["lrclib", "netease"]
NETEASE_FIRST = ["netease", "lrclib"]


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(User(id=7, email="u@example.com", created_at=0))
        s.add(User(id=8, email="other@example.com", created_at=0))
        s.commit()
        yield s


async def test_fetches_and_parses_on_first_lookup(db):
    netease = FakeSource("netease", tlyric="[00:01.00]你好")
    result = await LyricsService([netease]).get_lyrics(db, SONG, LRCLIB_FIRST)
    assert result.lines == [{"t": 1000, "text": "hello"}]
    assert result.translation_lines == [{"t": 1000, "text": "你好"}]
    assert (result.source, result.song_id, result.manual) == ("netease", "s1", False)


async def test_second_lookup_hits_cache_not_the_source(db):
    netease = FakeSource("netease")
    service = LyricsService([netease])
    await service.get_lyrics(db, SONG, LRCLIB_FIRST)
    await service.get_lyrics(db, SONG, LRCLIB_FIRST)
    assert len(netease.search_calls) == 1 and len(netease.fetch_calls) == 1


def test_source_order():
    cjk = TrackInfo("t", "稻香", "周杰伦", None)
    assert source_order(SONG, "auto", False) == LRCLIB_FIRST
    assert source_order(cjk, "auto", False) == NETEASE_FIRST
    assert source_order(SONG, "auto", True) == NETEASE_FIRST  # translations come from NetEase
    assert source_order(cjk, "lrclib", True) == LRCLIB_FIRST  # explicit choice wins
    assert source_order(SONG, "netease", False) == NETEASE_FIRST


async def test_latin_titles_try_lrclib_first_and_cjk_titles_netease(db):
    netease, lrclib = FakeSource("netease"), FakeSource("lrclib")
    service = LyricsService([netease, lrclib])
    assert (await service.get_lyrics(db, SONG, LRCLIB_FIRST)).source == "lrclib"
    assert netease.search_calls == []

    cjk = TrackInfo("track-2", "稻香", "周杰伦", 223_000)
    netease.hits = [Candidate("n2", "稻香", ["周杰伦"], 223_000, source="netease")]
    assert (await service.get_lyrics(db, cjk, source_order(cjk, "auto", False))).source == "netease"


async def test_falls_back_to_the_other_source(db):
    netease = FakeSource("netease", hits=[])
    lrclib = FakeSource("lrclib", hits=[Candidate("l9", "稻香", ["周杰伦"], 223_000, source="lrclib")])
    result = await LyricsService([netease, lrclib]).get_lyrics(db, TrackInfo("t", "稻香", "周杰伦", 223_000), NETEASE_FIRST)
    assert (result.source, result.song_id) == ("lrclib", "l9")


async def test_a_match_without_synced_lyrics_falls_through(db):
    lrclib = FakeSource("lrclib", lrc=None)
    netease = FakeSource("netease")
    result = await LyricsService([netease, lrclib]).get_lyrics(db, SONG, LRCLIB_FIRST)
    assert result.source == "netease"


async def test_no_match_caches_the_negative_result(db):
    netease = FakeSource("netease", hits=[])
    service = LyricsService([netease])
    assert (await service.get_lyrics(db, SONG, LRCLIB_FIRST)).lines == []
    calls = len(netease.search_calls)
    await service.get_lyrics(db, SONG, LRCLIB_FIRST)
    assert len(netease.search_calls) == calls


async def test_provider_outage_is_not_cached_as_no_lyrics(db):
    lrclib = FakeSource("lrclib", fail=True)
    service = LyricsService([lrclib])
    assert (await service.get_lyrics(db, SONG, LRCLIB_FIRST)).lines == []
    assert db.get(TrackMatch, (SONG.track_id, "lrclib")) is None
    lrclib.fail = False
    assert (await service.get_lyrics(db, SONG, LRCLIB_FIRST)).lines != []


async def test_rows_from_an_older_matcher_are_rematched(db):
    db.add(TrackMatch(spotify_track_id="track-1", title="Song", artist="Artist", source="lrclib", source_song_id="", match_version=MATCH_VERSION - 1, updated_at=0))
    db.commit()
    result = await LyricsService([FakeSource("lrclib")]).get_lyrics(db, SONG, LRCLIB_FIRST)
    assert result.lines == [{"t": 1000, "text": "hello"}]


async def test_manual_pick_is_shared_and_survives_rematching(db):
    netease, lrclib = FakeSource("netease"), FakeSource("lrclib", lrc="[00:02.00]picked")
    service = LyricsService([netease, lrclib])
    await service.get_lyrics(db, SONG, LRCLIB_FIRST)

    picked = await service.choose(db, SONG, "lrclib", "other-id", user_id=7)
    assert picked.manual and picked.lines == [{"t": 2000, "text": "picked"}]
    row = db.get(TrackMatch, ("track-1", "lrclib"))
    assert row.chosen_by == 7

    row.match_version = 0  # even an outdated row isn't re-matched when it's manual
    db.add(row)
    db.commit()
    again = await service.get_lyrics(db, SONG, LRCLIB_FIRST)
    assert (again.source, again.song_id, again.manual) == ("lrclib", "other-id", True)


async def test_pick_without_synced_lyrics_is_refused(db):
    service = LyricsService([FakeSource("netease", lrc=None)])
    with pytest.raises(NoSyncedLyrics):
        await service.choose(db, SONG, "netease", "x", user_id=7)


async def test_candidates_merge_sources_best_first(db):
    netease = FakeSource("netease", hits=[Candidate("n1", "Song (伴奏)", ["Artist"], 200_000, source="netease")])
    lrclib = FakeSource("lrclib", hits=[Candidate("l1", "Song", ["Artist"], 200_000, source="lrclib")])
    found = await LyricsService([netease, lrclib]).candidates(SONG)
    assert [(c.candidate.source, c.candidate.song_id) for c in found] == [("lrclib", "l1"), ("netease", "n1")]


async def test_each_reader_gets_their_preferred_source_and_both_are_cached(db):
    netease = FakeSource("netease", lrc="[00:01.00]from netease", tlyric="[00:01.00]翻译")
    lrclib = FakeSource("lrclib", lrc="[00:01.00]from lrclib")
    service = LyricsService([netease, lrclib])

    english_reader = await service.get_lyrics(db, SONG, LRCLIB_FIRST)
    chinese_reader = await service.get_lyrics(db, SONG, NETEASE_FIRST)

    assert english_reader.source == "lrclib" and english_reader.translation_lines == []
    assert chinese_reader.source == "netease" and chinese_reader.translation_lines == [{"t": 1000, "text": "翻译"}]
    await service.get_lyrics(db, SONG, LRCLIB_FIRST)
    await service.get_lyrics(db, SONG, NETEASE_FIRST)
    assert len(netease.search_calls) == 1 and len(lrclib.search_calls) == 1


async def test_a_source_is_only_searched_when_the_reader_reaches_it(db):
    netease, lrclib = FakeSource("netease"), FakeSource("lrclib")
    await LyricsService([netease, lrclib]).get_lyrics(db, SONG, NETEASE_FIRST)
    assert lrclib.search_calls == []


def order_for(db, user_id, preference):
    return reader_order(db, user_id, SONG, preference, False)


async def test_picking_another_source_without_calling_it_wrong_is_personal(db):
    netease, lrclib = FakeSource("netease"), FakeSource("lrclib", lrc="[00:03.00]lrclib")
    service = LyricsService([netease, lrclib])
    assert (await service.get_lyrics(db, SONG, order_for(db, 7, "netease"))).source == "netease"

    await service.choose(db, SONG, "lrclib", "l1", user_id=7)  # "I just prefer LRCLIB here"

    assert (await service.get_lyrics(db, SONG, order_for(db, 7, "netease"))).source == "lrclib"
    assert (await service.get_lyrics(db, SONG, order_for(db, 8, "netease"))).source == "netease"


async def test_calling_the_shown_lyrics_wrong_skips_that_source_for_everyone(db):
    netease, lrclib = FakeSource("netease"), FakeSource("lrclib", lrc="[00:03.00]lrclib")
    service = LyricsService([netease, lrclib])
    await service.get_lyrics(db, SONG, NETEASE_FIRST)

    await service.choose(db, SONG, "lrclib", "l1", user_id=7, wrong_source="netease")

    other = await service.get_lyrics(db, SONG, order_for(db, 8, "netease"))
    assert (other.source, other.song_id) == ("lrclib", "l1")
    assert len(netease.search_calls) == 1  # the rejected source is not searched again
    row = db.get(TrackMatch, ("track-1", "netease"))
    assert row.manual and row.source_song_id == "" and row.chosen_by == 7


async def test_a_correction_within_a_source_is_global_but_only_for_that_source(db):
    netease, lrclib = FakeSource("netease"), FakeSource("lrclib")
    service = LyricsService([netease, lrclib])
    await service.get_lyrics(db, SONG, NETEASE_FIRST)

    await service.choose(db, SONG, "netease", "right-one", user_id=7)

    assert (await service.get_lyrics(db, SONG, order_for(db, 8, "netease"))).song_id == "right-one"
    assert (await service.get_lyrics(db, SONG, order_for(db, 8, "lrclib"))).source == "lrclib"


async def test_a_later_pick_moves_the_readers_own_pin(db):
    service = LyricsService([FakeSource("netease"), FakeSource("lrclib")])
    await service.choose(db, SONG, "lrclib", "l", user_id=7)
    await service.choose(db, SONG, "netease", "n", user_id=7)
    assert (await service.get_lyrics(db, SONG, order_for(db, 7, "lrclib"))).source == "netease"


async def test_re_picking_the_automatic_match_is_not_a_correction(db):
    lrclib = FakeSource("lrclib")
    service = LyricsService([FakeSource("netease"), lrclib])
    await service.get_lyrics(db, SONG, LRCLIB_FIRST)  # lrclib auto-matches s1

    await service.choose(db, SONG, "lrclib", "s1", user_id=7)

    row = db.get(TrackMatch, ("track-1", "lrclib"))
    assert not row.manual and row.chosen_by is None
    assert (await service.get_lyrics(db, SONG, order_for(db, 7, "netease"))).source == "lrclib"  # still pinned


async def test_without_netease_every_reader_gets_lrclib(db):
    # Deployments without a NetEase service: whatever the preference, only LRCLIB exists.
    lrclib = FakeSource("lrclib")
    service = LyricsService([lrclib])
    assert (await service.get_lyrics(db, SONG, NETEASE_FIRST)).source == "lrclib"
    assert service.source_names == ["lrclib"]
