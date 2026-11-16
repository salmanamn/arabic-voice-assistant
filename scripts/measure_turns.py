"""Time budget check: every recording of a test set goes through the running gateway as one turn.

uv run python scripts/measure_turns.py [--set own] [--url http://127.0.0.1:8080]

Needs the three services and Ollama running. One warm-up turn is not counted. Reports p50/p90 per stage
(stt, chat, tts, other = total minus the three) and the peak memory of each service process, and writes
out/m3/turns.json for scripts/m3_report.py.
"""

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import httpx

from voice.quality import percentile
from voice.settings import load
from voice.speechset import read_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "speech"
OUT = ROOT / "out" / "m3"
SERVICES = {"stt": "voice.services.stt_app", "tts": "voice.services.tts_app", "gateway": "voice.services.gateway_app"}


def peak_memory_mb() -> dict[str, float | None]:
    """Peak resident memory (VmHWM) of each service process, found by its module in the command line."""
    found: dict[str, float | None] = dict.fromkeys(SERVICES)
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmdline = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            if (proc / "comm").read_text().strip() == "uv":
                continue  # `uv run` is the parent; its own memory is small
            status = (proc / "status").read_text()
        except OSError:
            continue
        for name, module in SERVICES.items():
            if module in cmdline:
                kb = next(int(line.split()[1]) for line in status.splitlines() if line.startswith("VmHWM:"))
                found[name] = max(found[name] or 0, kb / 1024)
    return found


def ollama_models(base_url: str) -> list[dict]:
    root = base_url.removesuffix("/").removesuffix("/v1")
    try:
        with urllib.request.urlopen(f"{root}/api/ps", timeout=5) as response:  # noqa: S310 (local endpoint)
            return [{"name": m["name"], "gb": round(m["size"] / 1e9, 2)} for m in json.load(response)["models"]]
    except (OSError, ValueError, KeyError):
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", default="own", choices=["own", "fleurs"])
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    settings = load()
    utterances = read_manifest(DATA / args.set)
    client = httpx.Client(base_url=args.url, timeout=300.0)

    def turn(path: Path) -> dict:
        with path.open("rb") as fh:
            response = client.post("/api/turn", files={"file": (path.name, fh, "application/octet-stream")})
        body = response.json()
        if response.status_code != 200:
            return {"status": response.status_code, "error": body.get("error", {}).get("code", "?")}
        return {"status": 200, "heard": body["heard"], "answer": body["answer"], "timings": body["timings"]}

    warm = turn(DATA / args.set / utterances[0].file)
    if warm["status"] != 200:
        print(f"warm-up turn failed: {warm['status']} {warm['error']} (are the services and Ollama up?)")
        return 1

    rows = []
    for u in utterances:
        result = turn(DATA / args.set / u.file)
        if result["status"] != 200:
            print(f"{u.id}  {result['status']} {result['error']}")
            rows.append({"id": u.id, **result})
            continue
        t = result["timings"]
        t["other"] = round(t["total"] - t.get("stt", 0) - t.get("chat", 0) - t.get("tts", 0), 2)
        rows.append({"id": u.id, "status": 200, "audio_seconds": u.seconds, "timings": t})
        print(
            f"{u.id}  audio {u.seconds:4.1f} s  stt {t['stt']:5.2f}  chat {t.get('chat', 0):5.2f}  "
            f"tts {t.get('tts', 0):5.2f}  other {t['other']:4.2f}  total {t['total']:5.2f}  | {result['answer']}"
        )

    ok = [r for r in rows if r["status"] == 200]
    stages = {}
    for stage in ("stt", "chat", "tts", "other", "total"):
        values = [r["timings"].get(stage, 0.0) for r in ok]
        stages[stage] = {"p50": percentile(values, 0.5), "p90": percentile(values, 0.9), "max": max(values or [0])}
    memory = peak_memory_mb()
    models = ollama_models(settings.openai_base_url)
    summary = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "set": args.set,
        "stt_model": settings.stt_model,
        "stt_threads": settings.stt_threads,
        "chat_model": settings.chat_model,
        "n": len(rows),
        "failed": len(rows) - len(ok),
        "stages": stages,
        "memory_mb": memory,
        "ollama": models,
        "rows": rows,
    }
    print()
    print(f"{len(ok)}/{len(rows)} turns, {settings.stt_model} ({settings.stt_threads} threads) + {settings.chat_model}")
    for stage, s in stages.items():
        print(f"  {stage:6} p50 {s['p50']:5.2f} s  p90 {s['p90']:5.2f} s  max {s['max']:5.2f} s")
    print("  peak memory: " + ", ".join(f"{k} {v:.0f} MB" if v else f"{k} not found" for k, v in memory.items()))
    print("  ollama: " + (", ".join(f"{m['name']} {m['gb']} GB" for m in models) or "not reachable"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "turns.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote out/m3/turns.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
