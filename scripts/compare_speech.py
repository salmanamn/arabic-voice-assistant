"""Azure AI Speech against faster-whisper and Piper on the same test turns (the optional M9 evening, D59).

uv run python scripts/compare_speech.py run --kube voice --out ~/m9/speech-pods.json [--audio-dir ~/m9/audio]
uv run python scripts/compare_speech.py report ~/m9/speech-pods.json ~/m9/speech-azure.json \
    --evidence docs/evidence/m9-speech.md

`run` sends every recording of the `own` set (D15) through the running gateway (`kubectl port-forward svc/gateway
8080:8080`) as one turn, after one warm-up turn. Each recording is first converted to 16 kHz mono 16-bit WAV, the
one PCM format Azure Speech's short-audio API takes, so both backends get the same bytes. Which backend served the
turns is asked from the gateway pod itself (STT_BACKEND, TTS_BACKEND), not typed in. Per turn it keeps what was
heard, its character and word error rate against the prompt (D8's scoring), the gateway's stage times and the
answer's length; with --audio-dir it also saves the first three answers' audio for listening (not for git).

`report` puts two or more runs side by side: time per stage against the budget (D18), recognition errors (all,
Modern Standard Arabic, Gulf), and one line per recording. The answers differ between runs (the chat model is not
deterministic), so text to speech is also given per 100 characters of answer.
"""

import argparse
import base64
import io
import json
import subprocess
import sys
import wave
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np

from voice.quality import BUDGET, percentile
from voice.speechset import read_manifest
from voice.stt import SAMPLE_RATE, SpeechToText
from voice.textnorm import score, total

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "speech"
ASK_BACKENDS = "from voice.settings import load; s = load(); print(s.stt_backend, s.tts_backend)"


def as_wav(path: Path) -> bytes:
    """The recording as 16 kHz mono 16-bit PCM WAV (decoded with PyAV, as the stt service decodes it)."""
    samples = SpeechToText.decode(path)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(pcm)
    return buffer.getvalue()


def gateway_backends(namespace: str) -> str:
    result = subprocess.run(  # noqa: S603 (kubectl with fixed arguments)
        ["kubectl", "-n", namespace, "exec", "deploy/gateway", "-c", "gateway", "--", "python", "-c", ASK_BACKENDS],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"could not ask the gateway pod for its backends: {result.stderr.strip()[-200:]}")
    stt, tts = result.stdout.split()
    return f"stt {stt}, tts {tts}"


def run(args: argparse.Namespace) -> int:
    backends = gateway_backends(args.kube)
    utterances = read_manifest(DATA / "own")
    client = httpx.Client(base_url=args.url, timeout=120.0)

    def turn(data: bytes) -> tuple[int, dict]:
        response = client.post("/api/turn", files={"file": ("question.wav", data, "audio/wav")})
        return response.status_code, response.json()

    status, body = turn(as_wav(DATA / "own" / utterances[0].file))
    if status != 200:
        print(f"warm-up turn failed: {status} {body.get('error', {}).get('code', '?')} ({backends})")
        return 1
    if args.audio_dir:
        args.audio_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for n, u in enumerate(utterances):
        status, body = turn(as_wav(DATA / "own" / u.file))
        if status != 200:
            code = body.get("error", {}).get("code", "?")
            rows.append({"id": u.id, "style": u.style, "status": status, "error": code})
            print(f"{u.id}  {status} {code}")
            continue
        result = score(u.text, body["heard"])
        t = body["timings"]
        rows.append(
            {
                "id": u.id,
                "style": u.style,
                "status": 200,
                "heard": body["heard"],
                "answer_chars": len(body["answer"]),
                "errors": {"words": result.word_errors, "ref_words": result.ref_words},
                "char_errors": {"chars": result.char_errors, "ref_chars": result.ref_chars},
                "cer": round(result.cer, 4),
                "timings": t,
            }
        )
        if args.audio_dir and n < 3 and body.get("audio"):
            name = f"{backends.replace(', ', '-').replace(' ', '_')}-{u.id}.wav"
            (args.audio_dir / name).write_bytes(base64.b64decode(body["audio"]))
        print(
            f"{u.id}  CER {result.cer:6.1%}  stt {t['stt']:5.2f}  chat {t.get('chat', 0):5.2f}  "
            f"tts {t.get('tts', 0):5.2f}  total {t['total']:5.2f}  | {body['heard']}"
        )

    summary = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "backends": backends,
        "set": "own",
        "n": len(rows),
        "failed": sum(r["status"] != 200 for r in rows),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = [r for r in rows if r["status"] == 200]
    print(f"\n{len(ok)}/{len(rows)} turns ({backends}); wrote {args.out}")
    return 0 if ok else 1


def corpus(rows: list[dict], style: str | None = None) -> str:
    from voice.textnorm import Score

    chosen = [r for r in rows if r["status"] == 200 and (style is None or r["style"] == style)]
    if not chosen:
        return "—"
    s = total(
        Score(r["errors"]["words"], r["errors"]["ref_words"], r["char_errors"]["chars"], r["char_errors"]["ref_chars"])
        for r in chosen
    )
    return f"{s.cer:.1%} / {s.wer:.1%} ({len(chosen)})"


def stage(rows: list[dict], name: str) -> list[float]:
    return [r["timings"][name] for r in rows if r["status"] == 200 and name in r["timings"]]


def report(args: argparse.Namespace) -> int:
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in args.runs]
    heads = [f"{r['backends']} ({r['date']})" for r in runs]
    budgets = {"stt": BUDGET.stt, "chat": BUDGET.chat, "tts": BUDGET.tts, "total": BUDGET.total}
    lines = [
        "# Azure AI Speech against faster-whisper and Piper on AKS (M9, D59)",
        "",
        "`scripts/compare_speech.py`: the 20 recordings of the `own` set (14 Modern Standard Arabic, 6 Gulf), each",
        "converted once to 16 kHz mono WAV and sent through the gateway as one turn, after one warm-up turn. Same",
        "cluster, same gateway, same chat model; only the gateway's speech backends differ (asked from the pod).",
        "",
        "| | " + " | ".join(heads) + " | Budget |",
        "|---|" + "---|" * len(runs) + "---|",
        "| turns ok | " + " | ".join(f"{r['n'] - r['failed']}/{r['n']}" for r in runs) + " | |",
    ]
    for name, budget in budgets.items():
        cells = []
        for r in runs:
            values = stage(r["rows"], name)
            p90 = percentile(values, 0.9)
            mark = "" if p90 <= budget else " OVER"
            cells.append(f"{percentile(values, 0.5):.2f} / {p90:.2f}{mark}" if values else "—")
        lines.append(f"| {name} p50 / p90 s | " + " | ".join(cells) + f" | {budget:g} |")
    cells = []
    for r in runs:
        ok = [x for x in r["rows"] if x["status"] == 200 and x.get("answer_chars")]
        per_100 = [x["timings"]["tts"] / x["answer_chars"] * 100 for x in ok if "tts" in x["timings"]]
        cells.append(f"{percentile(per_100, 0.5):.2f}" if per_100 else "—")
    lines.append("| tts s per 100 answer chars (p50) | " + " | ".join(cells) + " | |")
    for label, style in (("all", None), ("MSA", "msa"), ("Gulf", "gulf")):
        lines.append(f"| CER / WER, {label} (n) | " + " | ".join(corpus(r["rows"], style) for r in runs) + " | |")
    empty = [sum(1 for x in r["rows"] if x["status"] == 200 and not x["heard"]) for r in runs]
    lines.append("| heard nothing | " + " | ".join(str(e) for e in empty) + " | |")
    errors = [", ".join(f"{x['id']} {x['error']}" for x in r["rows"] if x["status"] != 200) or "none" for r in runs]
    lines.append("| failed turns | " + " | ".join(errors) + " | |")

    lines += ["", "Per recording, character error rate and what was heard:", ""]
    lines.append(
        "| id | style | "
        + " | ".join(f"CER {i + 1}" for i in range(len(runs)))
        + " | "
        + " | ".join(f"heard {i + 1}" for i in range(len(runs)))
        + " |"
    )
    lines.append("|---|---|" + "---|" * (2 * len(runs)))
    by_id = [{x["id"]: x for x in r["rows"]} for r in runs]
    for u in runs[0]["rows"]:
        cells = [by_id[i].get(u["id"], {}) for i in range(len(runs))]
        cers = [f"{c['cer']:.0%}" if c.get("status") == 200 else str(c.get("error", "—")) for c in cells]
        heard = [c.get("heard", "").replace("|", "/") for c in cells]
        lines.append(f"| {u['id']} | {u['style']} | " + " | ".join(cers) + " | " + " | ".join(heard) + " |")
    lines += [
        "",
        "Columns: " + "; ".join(f"{i + 1} = {h}" for i, h in enumerate(heads)) + ".",
        "",
    ]
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:22]))
    print(f"wrote {args.evidence}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("run", help="one pass over the own set through the gateway")
    one.add_argument("--kube", metavar="NAMESPACE", default="voice", help="where the gateway pod runs")
    one.add_argument("--url", default="http://127.0.0.1:8080", help="the gateway (port-forward)")
    one.add_argument("--out", type=Path, required=True, help="JSON of this run")
    one.add_argument("--audio-dir", type=Path, help="save the first three answers' audio here (not for git)")
    both = sub.add_parser("report", help="two or more runs side by side")
    both.add_argument("runs", type=Path, nargs="+")
    both.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    return run(args) if args.command == "run" else report(args)


if __name__ == "__main__":
    sys.exit(main())
