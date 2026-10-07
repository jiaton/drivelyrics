from app.lyrics.lrc_parser import parse_lrc


def test_basic_line():
    assert parse_lrc("[00:04.63]Took your heart took your hand") == [
        {"t": 4630, "text": "Took your heart took your hand"}
    ]


def test_multiple_timestamps_share_one_line():
    # A repeated chorus line often gets multiple cue points on one LRC line.
    lines = parse_lrc("[00:10.00][00:20.00]La la la")
    assert lines == [
        {"t": 10000, "text": "La la la"},
        {"t": 20000, "text": "La la la"},
    ]


def test_empty_line_kept_as_a_gap_cue():
    lines = parse_lrc("[00:06.37]")
    assert lines == [{"t": 6370, "text": ""}]


def test_lines_without_a_timestamp_are_dropped():
    assert parse_lrc("just plain text, no tag") == []


def test_sorted_by_time_regardless_of_source_order():
    raw = "[00:20.00]second\n[00:10.00]first"
    lines = parse_lrc(raw)
    assert [l["t"] for l in lines] == [10000, 20000]


def test_metadata_credit_lines_are_stripped():
    # Confirmed live 2026-09-13: NetEase bakes these into the LRC body as real timed
    # cues (not header tags), so they'd otherwise render as the opening "lyrics".
    raw = (
        "[00:00.00]作词 : Dan Reynolds\n"
        "[00:01.00]作曲 : Dan Reynolds\n"
        "[00:04.63]Took your heart took your hand"
    )
    lines = parse_lrc(raw)
    assert lines == [{"t": 4630, "text": "Took your heart took your hand"}]


def test_english_credit_labels_are_also_stripped():
    raw = "[00:00.00]Lyrics by: Someone\n[00:04.63]Real lyric line"
    lines = parse_lrc(raw)
    assert lines == [{"t": 4630, "text": "Real lyric line"}]


def test_frac_digit_counts_are_all_handled():
    # LRC allows 1-3 fractional digits ([mm:ss.x], [mm:ss.xx], [mm:ss.xxx]).
    assert parse_lrc("[00:01.5]a")[0]["t"] == 1500
    assert parse_lrc("[00:01.50]a")[0]["t"] == 1500
    assert parse_lrc("[00:01.500]a")[0]["t"] == 1500
