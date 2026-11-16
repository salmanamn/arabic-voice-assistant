"""M3 summary: compare the measurements, apply the choice rules (voice.quality), check the time budget.

uv run python scripts/m3_report.py            print the summary and write docs/evidence/m3-summary.md
uv run python scripts/m3_report.py --apply    also make the chosen models the defaults and fill in the decisions

Reads out/m3/stt-own-*.json and stt-fleurs-*.json (scripts/eval_stt.py), out/m3/chat.json (eval_chat.py) and,
when it exists, out/m3/turns.json (measure_turns.py). --apply changes, by exact text replacement only:
src/voice/settings.py and tests/unit/test_settings.py (the STT_MODEL / CHAT_MODEL / CHAT_REASONING_EFFORT
defaults), the two README commands that name those models, and the {{...}} placeholders in docs/decisions.md.
Running it again is safe: what is already applied is left as it is.
"""

import argparse
import json
import sys
from pathlib import Path

from voice.quality import BUDGET, Choice, choose_chat, choose_stt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "m3"
EVIDENCE = ROOT / "docs" / "evidence" / "m3-summary.md"
DEFAULT_STT, DEFAULT_CHAT = "stt-small", "phi4-mini:3.8b"  # the defaults before M3


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def stt_section(lines: list[str]) -> Choice:
    results = {}
    by_model: dict[str, dict] = {}
    for path in sorted(OUT.glob("stt-*.json")):
        data = load_json(path)
        by_model.setdefault(data["model"], {})[data["set"]] = data
    if not by_model:
        raise SystemExit("no out/m3/stt-*.json: run scripts/eval_stt.py first")
    lines += [
        "## Speech to text",
        "",
        "| Model | Set | n | CER | WER | p50 s | p90 s | RTF | Threads |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for model, sets in sorted(by_model.items()):
        for name, d in sorted(sets.items(), reverse=True):  # own first
            lines.append(
                f"| `{model}` | {name} | {d['n']} | {d['cer']:.1%} | {d['wer']:.1%} | {d['p50']:.2f} | {d['p90']:.2f} "
                f"| {d['rtf']:.2f} | {d['threads']} |"
            )
        if "own" in sets:
            results[model] = {"cer": sets["own"]["cer"], "p90": sets["own"]["p90"]}
    styles = [
        f"- `{model}` {name}/{style}: n={s['n']}, CER {s['cer']:.1%}, WER {s['wer']:.1%}"
        for model, sets in sorted(by_model.items())
        for name, d in sorted(sets.items(), reverse=True)
        for style, s in d["by_style"].items()
    ]
    lines += ["", "By style:", "", *styles, ""]
    if not results:
        raise SystemExit("no own-set results: the choice is made on your recordings (eval_stt.py --set own)")
    choice = choose_stt(results)
    lines += [f"**Choice: `{choice.model}`** — {choice.reason}.", ""]
    return choice


def chat_section(lines: list[str]) -> Choice:
    path = OUT / "chat.json"
    if not path.is_file():
        raise SystemExit("no out/m3/chat.json: run scripts/eval_chat.py first")
    models = [m for m in load_json(path)["models"] if "failed" not in m]
    lines += [
        "## Chat model",
        "",
        "| Model | Correct | Arabic | Errors | p50 s | p90 s | tok/s | Memory GB |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in models:
        memory = f"{m['memory_gb']:.1f}" if m["memory_gb"] is not None else "?"
        lines.append(
            f"| `{m['spec']}` | {m['correct']:.0%} | {m['arabic']:.0%} | {m['errors']} | {m['p50']:.2f} "
            f"| {m['p90']:.2f} | {m['tokens_per_second']:.1f} | {memory} |"
        )
    choice = choose_chat({m["spec"]: m for m in models})
    effort = f" with `CHAT_REASONING_EFFORT={choice.reasoning_effort}`" if choice.reasoning_effort else ""
    lines += ["", f"**Choice: `{choice.model}`**{effort} — {choice.reason}.", ""]
    return choice


def budget_section(lines: list[str], stt: Choice, chat: Choice) -> str | None:
    path = OUT / "turns.json"
    rows = [
        ("stt", BUDGET.stt),
        ("chat", BUDGET.chat),
        ("tts", BUDGET.tts),
        ("other", BUDGET.other),
        ("total", BUDGET.total),
    ]
    lines += ["## Time budget (end of question to answer audio, warm, laptop)", ""]
    if not path.is_file():
        lines += ["| Stage | Budget p90 s |", "|---|---|", *[f"| {s} | {b:g} |" for s, b in rows], ""]
        lines += ["Not measured yet: run scripts/measure_turns.py with the chosen models.", ""]
        return None
    turns = load_json(path)
    lines += [
        f"Measured {turns['date']}: {turns['n'] - turns['failed']}/{turns['n']} turns of the `{turns['set']}` set, "
        f"`{turns['stt_model']}` ({turns['stt_threads']} threads) + `{turns['chat_model']}`.",
        "",
        "| Stage | Budget p90 s | Measured p50 s | Measured p90 s | |",
        "|---|---|---|---|---|",
    ]
    over = []
    for stage, budget in rows:
        s = turns["stages"][stage]
        ok = s["p90"] <= budget
        if not ok:
            over.append(f"{stage} p90 {s['p90']:.2f} s > {budget:g} s")
        lines.append(f"| {stage} | {budget:g} | {s['p50']:.2f} | {s['p90']:.2f} | {'OK' if ok else 'OVER'} |")
    memory = ", ".join(f"{k} {v:.0f} MB" for k, v in turns["memory_mb"].items() if v)
    ollama = ", ".join(f"{m['name']} {m['gb']} GB" for m in turns["ollama"])
    lines += ["", f"Peak memory: {memory or 'not found'}; Ollama: {ollama or 'not reachable'}.", ""]
    total = turns["stages"]["total"]
    verdict = f"p50 {total['p50']:.2f} s / p90 {total['p90']:.2f} s against {BUDGET.total:g} s"
    verdict += f"; over: {'; '.join(over)}" if over else "; every stage within budget"
    if turns["failed"]:
        verdict += f"; {turns['failed']} turns failed"
    lines += [f"**Budget: {verdict}.**", ""]
    if (turns["stt_model"], turns["chat_model"]) != (stt.model, chat.model):
        lines += [f"These turns ran other models than the choice (`{stt.model}` + `{chat.model}`): measure again.", ""]
        return None
    return f"{verdict} (`{turns['stt_model']}` + `{turns['chat_model']}`, {turns['date']})"


def replace_once(path: Path, old: str, new: str, changed: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    if old == new or (old not in text and new in text):
        return  # nothing to do, or already applied
    if text.count(old) != 1:
        raise SystemExit(f"{path.relative_to(ROOT)}: expected exactly one {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")
    changed.append(str(path.relative_to(ROOT)))


def apply(stt: Choice, chat: Choice, budget: str | None) -> None:
    changed: list[str] = []
    settings, tests, readme = ROOT / "src/voice/settings.py", ROOT / "tests/unit/test_settings.py", ROOT / "README.md"
    replace_once(settings, f'"STT_MODEL", "{DEFAULT_STT}"', f'"STT_MODEL", "{stt.model}"', changed)
    replace_once(settings, f'"CHAT_MODEL", "{DEFAULT_CHAT}"', f'"CHAT_MODEL", "{chat.model}"', changed)
    replace_once(
        settings,
        '"CHAT_REASONING_EFFORT", "")',
        f'"CHAT_REASONING_EFFORT", "{chat.reasoning_effort}")',
        changed,
    )
    replace_once(tests, f'Path("models/{DEFAULT_STT}")', f'Path("models/{stt.model}")', changed)
    replace_once(tests, f'settings.chat_model == "{DEFAULT_CHAT}"', f'settings.chat_model == "{chat.model}"', changed)
    replace_once(
        tests,
        'settings.chat_reasoning_effort == ""',
        f'settings.chat_reasoning_effort == "{chat.reasoning_effort}"',
        changed,
    )
    replace_once(readme, f"fetch_models.py {DEFAULT_STT} tts-", f"fetch_models.py {stt.model} tts-", changed)
    replace_once(readme, f"ollama pull {DEFAULT_CHAT}", f"ollama pull {chat.model}", changed)
    decisions = ROOT / "docs/decisions.md"
    effort = f", `CHAT_REASONING_EFFORT={chat.reasoning_effort}`" if chat.reasoning_effort else ""
    fills = {
        "{{STT_CHOICE}}": f"`{stt.model}`",
        "{{STT_REASON}}": stt.reason,
        "{{CHAT_CHOICE}}": f"`{chat.model}`{effort}",
        "{{CHAT_REASON}}": chat.reason,
    }
    if budget:
        fills["{{BUDGET_RESULT}}"] = budget
    text = decisions.read_text(encoding="utf-8")
    for key, value in fills.items():
        if key in text:
            text = text.replace(key, value)
            changed.append(f"docs/decisions.md {key}")
    decisions.write_text(text, encoding="utf-8")
    left = [key for key in ("{{STT_CHOICE}}", "{{CHAT_CHOICE}}", "{{BUDGET_RESULT}}") if key in text]
    print("applied: " + (", ".join(dict.fromkeys(changed)) or "nothing new"))
    print("placeholders left in docs/decisions.md: " + (", ".join(left) or "none"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="make the choices the defaults; fill in decisions.md")
    args = parser.parse_args()

    lines = ["# M3 summary: Arabic quality and the model choice", ""]
    stt = stt_section(lines)
    chat = chat_section(lines)
    budget = budget_section(lines, stt, chat)
    lines += [
        "Rules: `voice.quality.choose_stt` / `choose_chat`, budget `voice.quality.Budget` (decisions D16–D18).",
        "",
    ]
    EVIDENCE.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {EVIDENCE.relative_to(ROOT)}")
    flags = [name for name, c in (("speech to text", stt), ("chat", chat)) if not c.within_budget]
    print(f"STT_MODEL={stt.model} CHAT_MODEL={chat.model} CHAT_REASONING_EFFORT={chat.reasoning_effort}")
    if flags:
        print(f"NOTE: {' and '.join(flags)} outside the budget or quality bar (see the reasons above)")
    if args.apply:
        apply(stt, chat, budget)
    return 0


if __name__ == "__main__":
    sys.exit(main())
