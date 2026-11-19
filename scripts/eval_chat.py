"""Small chat models on Arabic questions with known answers: correctness, answer language, speed, memory.

uv run python scripts/eval_chat.py phi4-mini:3.8b gemma3:4b qwen3.5:4b@none

A model name ending in @none is a thinking model asked to answer without thinking (CHAT_REASONING_EFFORT=none).
Each model gets the product's own request (voice.llm.Assistant: same system prompt, temperature, token limit),
one warm-up call (its time is the load time) and then every question in eval/qa.jsonl once. Memory is what Ollama
reports for the loaded model (/api/ps). Writes out/m3/chat.json and docs/evidence/m3-chat.md.
"""

import argparse
import json
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import openai

from voice.llm import Assistant, credential
from voice.quality import answer_is_correct, percentile, split_spec
from voice.settings import load
from voice.textnorm import arabic_ratio, clean_for_speech

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "eval" / "qa.jsonl"
OUT = ROOT / "out" / "m3"
ARABIC = 0.9  # an answer counts as Arabic when at least 90 % of its letters are Arabic


def loaded_size_gb(base_url: str, model: str) -> float | None:
    """Resident size of `model` as Ollama reports it, in GB; None if the endpoint is not Ollama."""
    root = base_url.removesuffix("/").removesuffix("/v1")
    try:
        with urllib.request.urlopen(f"{root}/api/ps", timeout=5) as response:  # noqa: S310 (local endpoint from settings)
            models = json.load(response).get("models", [])
    except (OSError, ValueError):
        return None
    for entry in models:
        if model in (entry.get("name"), entry.get("model")):
            return entry.get("size", 0) / 1e9
    return None


def evaluate(spec: str, cases: list[dict], settings) -> dict:
    model, effort = split_spec(spec)
    assistant = Assistant(
        base_url=settings.openai_base_url,
        api_key=credential(settings),
        model=model,
        max_tokens=settings.chat_max_tokens,
        reasoning_effort=effort,
        timeout=300.0,
    )
    started = time.perf_counter()
    try:
        assistant.reply("مرحبا")  # loads the model; not counted
    except openai.OpenAIError as exc:
        print(f"{spec}: FAILED to load ({type(exc).__name__}: {getattr(exc, 'message', exc)})")
        return {"spec": spec, "failed": f"{type(exc).__name__}"}
    load_seconds = time.perf_counter() - started
    memory = loaded_size_gb(settings.openai_base_url, model)
    print(f"{spec}: loaded in {load_seconds:.1f} s" + (f", {memory:.1f} GB" if memory is not None else ""))

    rows = []
    for case in cases:
        try:
            reply = assistant.reply(case["question"])
            text, seconds, tokens, error = reply.text, reply.seconds, reply.completion_tokens, ""
        except openai.OpenAIError as exc:
            text, seconds, tokens, error = "", 0.0, None, type(exc).__name__
        spoken = clean_for_speech(text)
        row = {
            "id": case["id"],
            "answer": spoken,
            "seconds": round(seconds, 3),
            "tokens": tokens,
            "correct": answer_is_correct(spoken, case["accept"]),
            "arabic": bool(spoken) and arabic_ratio(spoken) >= ARABIC,
            "error": error or ("empty" if not spoken else ""),
        }
        rows.append(row)
        mark = "OK " if row["correct"] else "-- "
        lang = "" if row["arabic"] else " [not Arabic]"
        print(f"  {case['id']} {mark} {seconds:5.2f} s {tokens or 0:3} tok{lang} | {spoken or row['error']}")

    answered = [r for r in rows if not r["error"]]
    times = [r["seconds"] for r in answered]
    rates = [r["tokens"] / r["seconds"] for r in answered if r["tokens"] and r["seconds"]]
    summary = {
        "spec": spec,
        "n": len(rows),
        "correct": sum(r["correct"] for r in rows) / len(rows),
        "arabic": sum(r["arabic"] for r in rows) / len(rows),
        "errors": len(rows) - len(answered),
        "p50": percentile(times, 0.5),
        "p90": percentile(times, 0.9),
        "tokens_per_second": percentile(rates, 0.5),
        "median_chars": percentile([len(r["answer"]) for r in answered], 0.5),
        "load_seconds": round(load_seconds, 1),
        "memory_gb": memory,
        "rows": rows,
    }
    print(
        f"{spec}: {summary['correct']:.0%} correct, {summary['arabic']:.0%} Arabic, {summary['errors']} errors, "
        f"p50 {summary['p50']:.2f} s, p90 {summary['p90']:.2f} s, {summary['tokens_per_second']:.1f} tok/s\n"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="+", metavar="MODEL", help="Ollama model names, optionally with @none")
    args = parser.parse_args()

    settings = load()
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = [evaluate(spec, cases, settings) for spec in args.models]

    OUT.mkdir(parents=True, exist_ok=True)
    report = {"date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"), "endpoint": settings.openai_base_url}
    out_json = OUT / "chat.json"
    out_json.write_text(
        json.dumps({**report, "models": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    ok = [r for r in results if "failed" not in r]
    lines = [
        "# Chat models on Arabic questions with known answers",
        "",
        f"- Date: {report['date']}; endpoint {settings.openai_base_url}; {len(cases)} questions (`eval/qa.jsonl`)",
        f"- Request as the product sends it: `voice.llm.SYSTEM_PROMPT`, temperature 0.2, max {settings.chat_max_tokens}"
        " tokens; one warm-up call per model (its time is the load time); each question asked once.",
        "- Correct = an accepted answer appears as whole words after normalisation. Arabic = at least 90 % of the "
        "letters are Arabic. Memory = Ollama's resident size for the loaded model.",
        "",
        "| Model | Correct | Arabic | Errors | p50 s | p90 s | tok/s | Median chars | Load s | Memory GB |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in ok:
        memory = f"{r['memory_gb']:.1f}" if r["memory_gb"] is not None else "?"
        lines.append(
            f"| `{r['spec']}` | {r['correct']:.0%} | {r['arabic']:.0%} | {r['errors']} | {r['p50']:.2f} "
            f"| {r['p90']:.2f} | {r['tokens_per_second']:.1f} | {r['median_chars']:.0f} | {r['load_seconds']} "
            f"| {memory} |"
        )
    lines += [f"| `{r['spec']}` | failed: {r['failed']} |  |  |  |  |  |  |  |  |" for r in results if "failed" in r]
    lines += ["", "## Answers", "", "| Id | Question | " + " | ".join(f"`{r['spec']}`" for r in ok) + " |"]
    lines.append("|---|---|" + "---|" * len(ok))
    for i, case in enumerate(cases):
        cells = []
        for r in ok:
            row = r["rows"][i]
            mark = "✓" if row["correct"] else "✗"
            cells.append(f"{mark} {row['answer'] or row['error']}".replace("|", "/"))
        lines.append(f"| {case['id']} | {case['question']} | " + " | ".join(cells) + " |")
    lines.append("")
    evidence = ROOT / "docs" / "evidence" / "m3-chat.md"
    evidence.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_json.relative_to(ROOT)}, {evidence.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
