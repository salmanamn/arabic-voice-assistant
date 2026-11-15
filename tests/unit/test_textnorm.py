import pytest

from voice.textnorm import Score, arabic_ratio, clean_for_speech, edit_distance, normalize, score, total


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("مَرْحَبًا", "مرحبا"),  # diacritics
        ("غداً", "غدا"),  # tanween
        ("مرحبـــا", "مرحبا"),  # tatweel
        ("أريد إجابة آمنة ٱلآن", "اريد اجابه امنه الان"),  # alef forms, ta marbuta
        ("إلى المستشفى", "الي المستشفي"),  # alef maqsura
        ("ما هي عاصمة البحرين؟", "ما هي عاصمه البحرين"),  # Arabic question mark
        ("شكرا، هذا كل شيء.", "شكرا هذا كل شيء"),  # Arabic comma, full stop
        ("الساعة ٥ و ۷ دقائق", "الساعه 5 و 7 دقائق"),  # Arabic-Indic and extended digits
        ("  Hello,   WORLD!  ", "hello world"),
        ("\ufefb", "لا"),  # presentation-form ligature
        ("", ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_normalize_composes_combining_hamza_before_mapping():
    assert normalize("ا\u0654حمد") == normalize("أحمد") == "احمد"


@pytest.mark.parametrize(
    ("ref", "hyp", "distance"),
    [
        ("", "", 0),
        ("abc", "abc", 0),
        ("abc", "", 3),
        ("", "abc", 3),
        ("kitten", "sitting", 3),
        (["a", "b", "c"], ["a", "c"], 1),
        (["a", "b"], ["a", "x", "b"], 1),
    ],
)
def test_edit_distance(ref, hyp, distance):
    assert edit_distance(ref, hyp) == distance


def test_score_ignores_spelling_variants_and_punctuation():
    result = score("مرحبا، كيف يمكنني مساعدتك اليوم؟", "مرحباً كيف يمكنني مساعدتك اليوم")
    assert result == Score(word_errors=0, ref_words=5, char_errors=0, ref_chars=26)
    assert result.wer == 0.0
    assert result.cer == 0.0


def test_score_counts_a_wrong_word():
    result = score("متى يفتح المصرف أبوابه", "متى يفتح المصنع أبوابه")
    assert (result.word_errors, result.ref_words) == (1, 4)
    assert result.char_errors == 2  # ر -> ن, ف -> ع
    assert result.wer == 0.25


def test_wrong_word_boundary_costs_words_not_characters():
    result = score("يا ليت", "ياليت")
    assert result.char_errors == 0
    assert result.word_errors == 2


def test_score_with_empty_reference():
    assert score("", "").wer == 0.0
    assert score("", "كلمة").wer == 1.0
    assert score("كلمة", "").cer == 1.0


def test_total_is_corpus_level_not_a_mean_of_rates():
    short = Score(word_errors=1, ref_words=1, char_errors=4, ref_chars=4)
    long = Score(word_errors=0, ref_words=9, char_errors=0, ref_chars=36)
    combined = total([short, long])
    assert combined.wer == pytest.approx(0.1)
    assert combined.cer == pytest.approx(0.1)


@pytest.mark.parametrize(
    ("text", "ratio"),
    [
        ("عاصمة البحرين هي المنامة.", 1.0),
        ("The capital is Manama.", 0.0),
        ("123 ؟!", 0.0),
        ("نعم ok", 0.6),
    ],
)
def test_arabic_ratio(text, ratio):
    assert arabic_ratio(text) == pytest.approx(ratio)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("**عاصمة البحرين** هي _المنامة_.", "عاصمة البحرين هي المنامة."),
        ("- أولا\n- ثانيا", "أولا ثانيا"),
        ("1. أولا\n2) ثانيا", "أولا ثانيا"),
        ("# عنوان\nنص `كود`", "عنوان نص كود"),
        ("زر [الموقع](https://example.com/a) الآن", "زر الموقع الآن"),
        ("المصدر: https://example.com/page?x=1 انتهى", "المصدر: انتهى"),
        ("أهلا 😀 بك ✅", "أهلا بك"),
        ("السعر 5-10 دنانير", "السعر 5-10 دنانير"),  # a hyphen inside a line is not a list marker
        ("مرحبا\u200f بك", "مرحبا بك"),  # right-to-left mark
        ("   ", ""),
    ],
)
def test_clean_for_speech(raw, expected):
    assert clean_for_speech(raw) == expected
