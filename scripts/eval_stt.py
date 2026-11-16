"""Word and character error rates of a Whisper model on a real-speech test set, and its time per utterance.

uv run python scripts/eval_stt.py --set own --model stt-small
uv run python scripts/eval_stt.py --set fleurs --model stt-turbo

Writes out/m3/stt-<set>-<model>.json (for scripts/m3_report.py) and docs/evidence/m3-stt-<set>-<model>.md.
Run nothing else heavy meanwhile: the times are the point.
"""

import argparse
import dataclasses
import json
import platform
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from voice.quality import percentile
from voice.settings import load
from voice.speechset import read_manifest
from voice.stt import SpeechToText
from voice.textnorm import score, total

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "speech"
OUT = ROOT / "out" / "m3"


def cpu_model() -> str:
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown CPU"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", required=True, choices=["own", "fleurs"])
    parser.add_argument("--model", required=True, help="model directory under models/, e.g. stt-small")
    args = parser.parse_args()

    settings = dataclasses.replace(load(), stt_model=args.model)
    utterances = read_manifest(DATA / args.set)
    stt = SpeechToText.from_settings(settings)
    stt.transcribe(DATA / args.set / utterances[0].file)  # warm-up: loads the voice-activity model; not counted

    rows = []
    for u in utterances:
        transcript = stt.transcribe(DATA / args.set / u.file)
        result = score(u.text, transcript.text)
        rows.append({"utterance": u, "heard": transcript.text, "seconds": transcript.seconds, "score": result})
        print(
            f"{u.id}  CER {result.cer:6.1%}  WER {result.wer:6.1%}  audio {u.seconds:5.1f} s  "
            f"stt {transcript.seconds:5.2f} s  | {transcript.text}"
        )

    corpus = total(r["score"] for r in rows)
    times = [r["seconds"] for r in rows]
    audio = sum(r["utterance"].seconds for r in rows)
    by_style: dict[str, list] = defaultdict(list)
    for r in rows:
        by_style[r["utterance"].style].append(r["score"])
    styles = {s: {"n": len(v), "cer": total(v).cer, "wer": total(v).wer} for s, v in sorted(by_style.items())}
    summary = {
        "set": args.set,
        "model": args.model,
        "threads": settings.stt_threads,
        "beam": settings.stt_beam_size,
        "cpu": cpu_model(),
        "date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "n": len(rows),
        "audio_seconds": round(audio, 1),
        "cer": corpus.cer,
        "wer": corpus.wer,
        "p50": percentile(times, 0.5),
        "p90": percentile(times, 0.9),
        "max": max(times),
        "rtf": sum(times) / audio,
        "by_style": styles,
    }
    print()
    print(f"{args.model} on {args.set}: {len(rows)} utterances, {audio:.0f} s of audio, {settings.stt_threads} threads")
    print(f"CER {corpus.cer:.1%}  WER {corpus.wer:.1%}")
    for style, s in styles.items():
        print(f"  {style:12} n={s['n']:2}  CER {s['cer']:.1%}  WER {s['wer']:.1%}")
    print(
        f"time per utterance: p50 {summary['p50']:.2f} s, p90 {summary['p90']:.2f} s, max {summary['max']:.2f} s, "
        f"RTF {summary['rtf']:.2f}"
    )

    OUT.mkdir(parents=True, exist_ok=True)
    out_json = OUT / f"stt-{args.set}-{args.model}.json"
    detail = [
        {"id": r["utterance"].id, "cer": r["score"].cer, "wer": r["score"].wer, "seconds": round(r["seconds"], 3)}
        for r in rows
    ]
    out_json.write_text(json.dumps({**summary, "rows": detail}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Speech to text on real speech: `{args.model}` on the `{args.set}` set",
        "",
        f"- Date: {summary['date']}",
        f"- Machine: {summary['cpu']}, {settings.stt_threads} threads, compute type {settings.stt_compute_type}, "
        f"beam {settings.stt_beam_size}, language `{settings.language}`",
        f"- {len(rows)} utterances, {audio:.0f} s of audio. Scored after `voice.textnorm.normalize` (D8).",
        "",
        "| Id | Style | CER | WER | Audio s | STT s | Reference | Heard |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        u, s = r["utterance"], r["score"]
        lines.append(
            f"| {u.id} | {u.style} | {s.cer:.1%} | {s.wer:.1%} | {u.seconds:.1f} | {r['seconds']:.2f} "
            f"| {u.text} | {r['heard']} |"
        )
    lines += [
        "",
        f"- Corpus CER {corpus.cer:.1%}, WER {corpus.wer:.1%}",
        *[f"- {style}: n={s['n']}, CER {s['cer']:.1%}, WER {s['wer']:.1%}" for style, s in styles.items()],
        f"- Time per utterance: p50 {summary['p50']:.2f} s, p90 {summary['p90']:.2f} s, max {summary['max']:.2f} s, "
        f"RTF {summary['rtf']:.2f}",
        "",
    ]
    evidence = ROOT / "docs" / "evidence" / f"m3-stt-{args.set}-{args.model}.md"
    evidence.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_json.relative_to(ROOT)}, {evidence.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
