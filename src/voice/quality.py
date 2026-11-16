"""Arabic quality measurements: percentiles, answer checking, the time budget, and the rules that pick the models.

The evaluation scripts (scripts/eval_stt.py, eval_chat.py, measure_turns.py) measure; scripts/m3_report.py applies
the rules here to their results. The rules are code so that a re-run on new numbers picks the same way (D16, D17).
"""

import math
from dataclasses import dataclass

from voice.textnorm import normalize

# One-letter Arabic prefixes that attach to the next word: and, so, with/in, for/to, like.
_PREFIXES = "وفبلك"


def percentile(values: list[float], share: float) -> float:
    """Nearest-rank percentile (share 0.9 = p90): the smallest value with at least `share` of the values at or below
    it. Always one of the measured values, which suits small samples. 0.0 for no values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


def answer_is_correct(answer: str, accepted: list[str]) -> bool:
    """True if any accepted form appears in the answer as whole words, after normalisation (spelling variants,
    diacritics, digits). The first word may carry a one-letter prefix: "والمنامة" contains "المنامة"."""
    words = normalize(answer).split()
    for form in accepted:
        wanted = normalize(form).split()
        if not wanted:
            continue
        for start in range(len(words) - len(wanted) + 1):
            first = words[start]
            first_ok = first == wanted[0] or (first[:1] in _PREFIXES and first[1:] == wanted[0])
            if first_ok and words[start + 1 : start + len(wanted)] == wanted[1:]:
                return True
    return False


@dataclass(frozen=True)
class Budget:
    """Time from the end of the question to the start of the answer audio, warm, on the laptop (D18).
    Every limit is a p90 over the measured turns, in seconds; memory is the chat model's resident size."""

    stt: float = 2.5
    chat: float = 3.5
    tts: float = 0.8
    other: float = 0.2  # gateway, HTTP hops, base64 of the answer audio
    chat_memory_gb: float = 7.0  # leaves room for the speech services and Windows inside 16 GB
    min_chat_correct: float = 0.80  # below this a local chat model is a stand-in, not an assistant
    min_arabic_answers: float = 0.95  # share of answers that must be Arabic (D6)
    min_cer_gap: float = 0.01  # STT: CER differences below one point are noise on ~20 utterances

    @property
    def total(self) -> float:
        return round(self.stt + self.chat + self.tts + self.other, 2)


BUDGET = Budget()


@dataclass(frozen=True)
class Choice:
    model: str
    within_budget: bool
    reason: str
    reasoning_effort: str = ""  # chat only: "none" for a thinking model asked not to think


def choose_stt(results: dict[str, dict], budget: Budget = BUDGET) -> Choice:
    """results: model -> {"cer": own-set CER, "p90": own-set p90 seconds per utterance}.

    Within the budget, the lowest CER wins; a model less than `min_cer_gap` more accurate than a faster one does
    not (noise on a small set). Nothing within the budget: the fastest model, flagged.
    """
    if not results:
        raise ValueError("no speech-to-text results")
    eligible = {m: r for m, r in results.items() if r["p90"] <= budget.stt}
    over = ", ".join(f"{m} p90 {r['p90']:.2f} s" for m, r in sorted(results.items()) if m not in eligible)
    if not eligible:
        fastest = min(results, key=lambda m: results[m]["p90"])
        return Choice(
            fastest,
            False,
            f"no model within the {budget.stt:g} s budget ({over}); {fastest} is the fastest",
        )
    best = min(eligible, key=lambda m: (eligible[m]["cer"], eligible[m]["p90"]))
    fastest = min(eligible, key=lambda m: (eligible[m]["p90"], eligible[m]["cer"]))
    if fastest != best and eligible[fastest]["cer"] - eligible[best]["cer"] < budget.min_cer_gap:
        best = fastest
    r = eligible[best]
    reason = f"own-set CER {r['cer']:.1%} at p90 {r['p90']:.2f} s, within the {budget.stt:g} s budget"
    others = [f"{m} CER {x['cer']:.1%} p90 {x['p90']:.2f} s" for m, x in sorted(eligible.items()) if m != best]
    if others:
        reason += f"; also within budget: {', '.join(others)}"
    if over:
        reason += f"; over budget: {over}"
    return Choice(best, True, reason)


def split_spec(spec: str) -> tuple[str, str]:
    """ "qwen3.5:4b@none" -> ("qwen3.5:4b", "none"); "phi4-mini:3.8b" -> ("phi4-mini:3.8b", "")."""
    model, _, effort = spec.partition("@")
    return model, effort


def choose_chat(results: dict[str, dict], budget: Budget = BUDGET) -> Choice:
    """results: model spec -> {"correct", "arabic" (shares 0..1), "p50", "p90" (warm seconds), "memory_gb"
    (None if unknown), "errors" (failed or empty answers)}.

    Eligible: every answer arrived, Arabic answers >= min_arabic_answers, memory and p90 within budget. Among
    those, most correct answers, then the faster p50. Nothing eligible: the most correct model that fits in memory
    and answers in Arabic, flagged as over budget. `within_budget` also requires min_chat_correct.
    """
    if not results:
        raise ValueError("no chat results")

    def fits(r: dict) -> bool:
        return (
            r["errors"] == 0
            and r["arabic"] >= budget.min_arabic_answers
            and (r["memory_gb"] or 0) <= budget.chat_memory_gb
        )

    def why_not(r: dict) -> str:
        problems = []
        if r["errors"]:
            problems.append(f"{r['errors']} failed/empty")
        if r["arabic"] < budget.min_arabic_answers:
            problems.append(f"Arabic {r['arabic']:.0%}")
        if (r["memory_gb"] or 0) > budget.chat_memory_gb:
            problems.append(f"{r['memory_gb']:.1f} GB")
        if r["p90"] > budget.chat:
            problems.append(f"p90 {r['p90']:.2f} s")
        return ", ".join(problems)

    eligible = {m: r for m, r in results.items() if fits(r) and r["p90"] <= budget.chat}
    pool, in_time = (eligible, True) if eligible else ({m: r for m, r in results.items() if fits(r)}, False)
    if not pool:
        pool = results
    best = max(pool, key=lambda m: (pool[m]["correct"], -pool[m]["p50"]))
    r = pool[best]
    model, effort = split_spec(best)
    good_enough = r["correct"] >= budget.min_chat_correct
    reason = f"{r['correct']:.0%} correct, {r['arabic']:.0%} Arabic, p90 {r['p90']:.2f} s"
    if r["memory_gb"] is not None:
        reason += f", {r['memory_gb']:.1f} GB"
    if not in_time:
        reason += f"; no model within the {budget.chat:g} s budget"
    if not good_enough:
        reason += f"; below the {budget.min_chat_correct:.0%} correctness bar: a lab stand-in until Azure OpenAI (M8)"
    rejected = [f"{m} ({why_not(x)})" for m, x in sorted(results.items()) if m != best and why_not(x)]
    if rejected:
        reason += f"; ruled out: {', '.join(rejected)}"
    others = [f"{m} {x['correct']:.0%}" for m, x in sorted(eligible.items()) if m != best]
    if others:
        reason += f"; also eligible: {', '.join(others)}"
    return Choice(model, in_time and good_enough, reason, effort)
