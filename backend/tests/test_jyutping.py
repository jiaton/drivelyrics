from app.lyrics.jyutping import line_jyutping, looks_cantonese


def test_jyutping_of_a_line():
    assert line_jyutping("攔路雨偏似雪花") == "laan4 lou6 jyu5 pin1 ci5 syut3 faa1"


def test_simplified_is_read_as_traditional():
    # 风褛 read as Simplified gives 褛 leoi5; as 風褸, lau1 — the right reading.
    assert line_jyutping("这风褛我给你磨到有襟花").split()[2] == "lau1"


def test_latin_words_kept_punctuation_dropped():
    assert line_jyutping("Hey，我哋一齊行！") == "Hey ngo5 dei6 jat1 cai4 haang4"
    assert line_jyutping("All the way (oh)") == ""


def test_looks_cantonese():
    standard_chinese = "[00:01.00]攔路雨偏似雪花\n[00:05.00]飲泣的你凍嗎"
    assert looks_cantonese(standard_chinese, provider_romanized=True)
    assert not looks_cantonese(standard_chinese, provider_romanized=False)  # 富士山下 reads like any Mandarin song
    assert looks_cantonese("[00:01.00]佢話我哋冇嘢", provider_romanized=False)  # colloquial Cantonese
    assert not looks_cantonese("[00:01.00]佢", provider_romanized=False)  # one character doesn't decide
    assert not looks_cantonese("[00:01.00]夢ならばどれほどよかったでしょう", provider_romanized=True)  # Japanese
    assert not looks_cantonese("[00:01.00]Hello", provider_romanized=True)
