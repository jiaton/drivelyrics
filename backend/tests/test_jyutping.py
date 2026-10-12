from app.lyrics.jyutping import chinese_lyrics, colloquial_cantonese, line_jyutping


def test_jyutping_of_a_line():
    assert line_jyutping("攔路雨偏似雪花") == "laan4 lou6 jyu5 pin1 ci5 syut3 faa1"


def test_simplified_is_read_as_traditional():
    # 风褛 read as Simplified gives 褛 leoi5; as 風褸, lau1 — the right reading.
    assert line_jyutping("这风褛我给你磨到有襟花").split()[2] == "lau1"


def test_latin_words_kept_punctuation_dropped():
    assert line_jyutping("Hey，我哋一齊行！") == "Hey ngo5 dei6 jat1 cai4 haang4"
    assert line_jyutping("All the way (oh)") == ""


def test_chinese_lyrics_and_colloquial_cantonese():
    assert chinese_lyrics("[00:01.00]攔路雨偏似雪花")
    assert not chinese_lyrics("[00:01.00]夢ならばどれほどよかったでしょう")  # Japanese
    assert not chinese_lyrics("[00:01.00]Hello")
    assert colloquial_cantonese("[00:01.00]佢話我哋冇嘢")
    assert not colloquial_cantonese("[00:01.00]佢")  # one character doesn't decide
    assert not colloquial_cantonese("[00:01.00]攔路雨偏似雪花")  # 富士山下 reads like any Mandarin song
