from app.lyrics.cantonese_model import features, probability, written_for_cantonese

# Invented lines in each style (never a real song's text in the repo).
CANTONESE_STYLE = """[00:01.00]仍然記得當天你共我走過
[00:05.00]亦似風中一片葉 未知誰人會伴我一生
[00:09.00]只得一句無謂再講 便讓往事令我心痛
[00:13.00]但若有一日 幾多願望也不可再提"""
MANDARIN_STYLE = """[00:01.00]我們不是說好了嗎
[00:05.00]因為時間總是會變成回憶
[00:09.00]可是你的笑容還有所有的夢想
[00:13.00]就是我一直以為的一定會在"""


def test_word_usage_tells_the_styles_apart():
    assert written_for_cantonese(CANTONESE_STYLE)
    assert not written_for_cantonese(MANDARIN_STYLE)


def test_features_fold_scripts_and_skip_credits_and_repeats():
    grams = features("[00:00.50]作詞：某人\n" + MANDARIN_STYLE + "\n[00:20.00]我們不是說好了嗎")
    assert "我们" in grams and "們" not in grams  # compared in 简体
    assert "作" not in grams  # credit line skipped
    assert features("[00:01.00]太短了") is None


def test_probability_is_a_logistic_score():
    assert probability(set(), {"仍": 2.0}, bias=0.0) == 0.5
    assert probability({"仍"}, {"仍": 2.0}, bias=0.0) > 0.85
