"""The measurement helpers and the rules that pick the speech and chat models (D16, D17)."""

import pytest

from voice.quality import BUDGET, Budget, answer_is_correct, choose_chat, choose_stt, percentile, split_spec


@pytest.mark.parametrize(
    ("values", "share", "expected"),
    [
        ([], 0.9, 0.0),
        ([3.0], 0.9, 3.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0], 0.9, 9.0),
        ([10.0, 1.0, 5.0], 0.5, 5.0),  # order does not matter
        ([1.0] * 19 + [30.0], 0.9, 1.0),  # one slow outlier in 20 is not the p90
        ([1.0] * 17 + [30.0] * 3, 0.9, 30.0),  # three are
    ],
)
def test_percentile(values, share, expected):
    assert percentile(values, share) == expected


@pytest.mark.parametrize(
    ("answer", "accepted", "correct"),
    [
        ("عاصمة مملكة البحرين هي المنامة.", ["المنامة"], True),
        ("العاصمة مملكة البحرين هي مدينة البحرين.", ["المنامة"], False),  # phi4-mini's M2 answer
        ("عاصمتها المنامه", ["المنامة"], True),  # ta marbuta written as ha
        ("تقع في الرياض والمنامة قريبة", ["المنامة"], True),  # one-letter prefix on the first word
        ("الأسبوع فيه 17 يوما", ["7"], False),  # whole words only
        ("سبعة أيام، أي ٧ أيام.", ["7"], True),  # Arabic-Indic digit
        ("الناتج اثنان وأربعون", ["42", "اثنان وأربعون"], True),  # several words
        ("اثنان وخمسون", ["اثنان وأربعون"], False),
        ("", ["المنامة"], False),
        ("المنامة", [""], False),
    ],
)
def test_answer_is_correct(answer, accepted, correct):
    assert answer_is_correct(answer, accepted) is correct


def test_budget_adds_up():
    assert BUDGET.total == 7.0
    assert Budget(stt=1, chat=1, tts=1, other=1).total == 4


# --- speech to text ---------------------------------------------------------------------------------------


def test_stt_most_accurate_within_budget_wins():
    choice = choose_stt({"stt-small": {"cer": 0.08, "p90": 2.0}, "stt-turbo": {"cer": 0.03, "p90": 2.4}})
    assert (choice.model, choice.within_budget) == ("stt-turbo", True)


def test_stt_a_model_over_budget_is_not_chosen_however_accurate():
    choice = choose_stt({"stt-small": {"cer": 0.08, "p90": 2.0}, "stt-turbo": {"cer": 0.01, "p90": 4.5}})
    assert (choice.model, choice.within_budget) == ("stt-small", True)
    assert "over budget: stt-turbo p90 4.50 s" in choice.reason


def test_stt_a_gap_below_one_point_goes_to_the_faster_model():
    choice = choose_stt({"stt-small": {"cer": 0.045, "p90": 1.8}, "stt-turbo": {"cer": 0.040, "p90": 2.4}})
    assert choice.model == "stt-small"


def test_stt_nothing_within_budget_takes_the_fastest_and_says_so():
    choice = choose_stt({"stt-small": {"cer": 0.08, "p90": 3.0}, "stt-turbo": {"cer": 0.03, "p90": 6.0}})
    assert (choice.model, choice.within_budget) == ("stt-small", False)
    assert choice.reason.startswith("no model within the 2.5 s budget")


def test_stt_needs_results():
    with pytest.raises(ValueError):
        choose_stt({})


# --- chat ---------------------------------------------------------------------------------------------


def chat(correct, p90, *, arabic=1.0, memory=3.0, errors=0, p50=None):
    return {
        "correct": correct,
        "arabic": arabic,
        "p50": p50 or p90 / 2,
        "p90": p90,
        "memory_gb": memory,
        "errors": errors,
    }


def test_chat_most_correct_eligible_model_wins():
    choice = choose_chat({"phi4-mini:3.8b": chat(0.6, 2.0), "gemma3:4b": chat(0.9, 3.0), "big:7b": chat(1.0, 6.0)})
    assert (choice.model, choice.within_budget, choice.reasoning_effort) == ("gemma3:4b", True, "")
    assert "big:7b (p90 6.00 s)" in choice.reason


def test_chat_tie_goes_to_the_faster_p50():
    choice = choose_chat({"a:4b": chat(0.9, 3.0, p50=2.0), "b:4b": chat(0.9, 3.0, p50=1.0)})
    assert choice.model == "b:4b"


@pytest.mark.parametrize(
    "loser",
    [
        chat(1.0, 1.0, arabic=0.90),  # answers in another language
        chat(1.0, 1.0, memory=7.5),  # too big next to the speech services
        chat(1.0, 1.0, errors=1),  # an empty or failed answer
    ],
)
def test_chat_disqualifications(loser):
    choice = choose_chat({"loser:4b": loser, "ok:4b": chat(0.85, 3.0)})
    assert choice.model == "ok:4b"


def test_chat_thinking_model_keeps_its_effort():
    choice = choose_chat({"qwen3.5:4b@none": chat(0.9, 2.0), "phi4-mini:3.8b": chat(0.5, 1.0)})
    assert (choice.model, choice.reasoning_effort) == ("qwen3.5:4b", "none")


def test_chat_nothing_in_time_takes_the_most_correct_that_fits_and_flags_it():
    choice = choose_chat({"a:7b": chat(0.95, 6.0), "b:4b": chat(0.7, 4.0), "huge:12b": chat(1.0, 9.0, memory=9.0)})
    assert (choice.model, choice.within_budget) == ("a:7b", False)
    assert "no model within the 3.5 s budget" in choice.reason


def test_chat_below_the_correctness_bar_is_flagged():
    choice = choose_chat({"phi4-mini:3.8b": chat(0.5, 1.5)})
    assert (choice.model, choice.within_budget) == ("phi4-mini:3.8b", False)
    assert "below the 80% correctness bar" in choice.reason


def test_split_spec():
    assert split_spec("qwen3.5:4b@none") == ("qwen3.5:4b", "none")
    assert split_spec("phi4-mini:3.8b") == ("phi4-mini:3.8b", "")
