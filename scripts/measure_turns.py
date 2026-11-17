"""Time budget check: every recording of a test set goes through the running gateway as one turn.

uv run python scripts/measure_turns.py [--set own] [--url http://127.0.0.1:8080]
uv run python scripts/measure_turns.py --compose --out out/m4/turns-compose.json --evidence docs/evidence/m4-turns.md
uv run python scripts/measure_turns.py --kube voice --out out/m5/turns-kube.json --baseline out/m4/turns-compose.json \
    --evidence docs/evidence/m5-turns.md

Needs the three services and Ollama running. One warm-up turn is not counted. Reports p50/p90 per stage
(stt, chat, tts, other = total minus the three) and the peak memory of each service, and writes a JSON summary
(default out/m3/turns.json, read by scripts/m3_report.py).

Without --compose the services are processes on this machine (M2/M3): models and threads come from this shell's
settings, peak memory from /proc. With --compose they are the containers of docker-compose.yml: models, threads
and peak memory are asked from inside each container, next to its memory limit. With --kube NAMESPACE they are the
pods of the Helm chart (M5), reached through `kubectl port-forward svc/gateway 8080:8080`, and asked the same way
with `kubectl exec` (one pod per Deployment). --evidence writes a Markdown
comparison with the time budget (D18) and with an earlier measurement (--baseline, default out/m3/turns.json).
"""

import argparse
import json
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import httpx

from voice.quality import BUDGET, percentile
from voice.settings import load
from voice.speechset import read_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "speech"
DEFAULT_OUT = ROOT / "out" / "m3" / "turns.json"
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


CONTAINERS = {"stt": "voice-stt", "tts": "voice-tts", "gateway": "voice-gateway"}
# Runs inside a service container: the process's own peak (VmHWM of PID 1, comparable with /proc on the laptop),
# the container's memory limit (cgroup v2, then v1) and the settings the service really runs with.
PROBE = """
import json, pathlib
from voice.settings import load
def first(*paths):
    for path in paths:
        try:
            return pathlib.Path(path).read_text().strip()
        except OSError:
            pass
    return ""
status = pathlib.Path("/proc/1/status").read_text()
peak_kb = next(int(line.split()[1]) for line in status.splitlines() if line.startswith("VmHWM:"))
limit = first("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes")
limit_mb = int(limit) / 2**20 if limit.isdigit() and int(limit) < 2**60 else None
s = load()
print(json.dumps({"peak_mb": peak_kb / 1024, "limit_mb": limit_mb, "stt_model": s.stt_model,
                  "stt_threads": s.stt_threads, "chat_model": s.chat_model}))
"""


def exec_command(name: str, namespace: str | None) -> list[str]:
    """The command that runs a program inside one service: its compose container, or its Deployment's pod."""
    if namespace:
        return ["kubectl", "-n", namespace, "exec", f"deploy/{name}", "-c", name, "--"]
    return ["docker", "exec", CONTAINERS[name]]


def probe_containers(namespace: str | None = None) -> dict[str, dict]:
    """What each service container reports about itself; {} for a container that is not running."""
    found = {}
    for name in CONTAINERS:
        result = subprocess.run(  # noqa: S603 (fixed command, fixed container names)
            [*exec_command(name, namespace), "python", "-c", PROBE],
            capture_output=True,
            text=True,
            check=False,
        )
        found[name] = json.loads(result.stdout) if result.returncode == 0 else {}
    return found


def kube_replicas(namespace: str) -> int:
    result = subprocess.run(  # noqa: S603
        ["kubectl", "-n", namespace, "get", "deploy", "stt", "-o", "jsonpath={.status.readyReplicas}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return int(result.stdout or 0)


def kube_ollama_models(namespace: str) -> list[dict]:
    """Ollama's loaded models, asked from the gateway pod (the only pod the policies let reach Ollama, D29)."""
    ask = (
        "import json, urllib.request as u; "
        "print(json.dumps(json.load(u.urlopen('http://ollama:11434/api/ps', timeout=5))['models']))"
    )
    result = subprocess.run(  # noqa: S603
        [*exec_command("gateway", namespace), "python", "-c", ask], capture_output=True, text=True, check=False
    )
    try:
        return [{"name": m["name"], "gb": round(m["size"] / 1e9, 2)} for m in json.loads(result.stdout)]
    except (ValueError, KeyError):
        return []


def ollama_models(base_url: str) -> list[dict]:
    root = base_url.removesuffix("/").removesuffix("/v1")
    try:
        with urllib.request.urlopen(f"{root}/api/ps", timeout=5) as response:  # noqa: S310 (local endpoint)
            return [{"name": m["name"], "gb": round(m["size"] / 1e9, 2)} for m in json.load(response)["models"]]
    except (OSError, ValueError, KeyError):
        return []


def shown(path: Path) -> str:
    """A path as the user would type it: relative to the repository when it is inside it."""
    path = path.resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def write_evidence(path: Path, summary: dict, baseline: dict | None, baseline_name: str) -> None:
    """Markdown: this measurement against the time budget (D18) and, when there is one, an earlier measurement."""
    where = summary.get("where") or ("compose containers" if summary["compose"] else "processes on the laptop")
    lines = [
        f"# One turn through the services ({where})",
        "",
        f"- Date: {summary['date']}; {summary['n'] - summary['failed']}/{summary['n']} turns of the "
        f"`{summary['set']}` set after one warm-up turn",
        f"- Models: `{summary['stt_model']}` ({summary['stt_threads']} threads) + `{summary['chat_model']}`",
    ]
    if baseline:
        lines.append(
            f"- Compared with `{baseline_name}`: {baseline['date']}, `{baseline['stt_model']}` "
            f"({baseline['stt_threads']} threads) + `{baseline['chat_model']}`"
        )
    else:
        lines.append(f"- No earlier measurement to compare with (`{baseline_name}` not found)")
    budgets = {"stt": BUDGET.stt, "chat": BUDGET.chat, "tts": BUDGET.tts, "other": BUDGET.other, "total": BUDGET.total}
    lines += [
        "",
        "| Stage | Budget p90 s | Before p50 s | Before p90 s | Now p50 s | Now p90 s | p90 change s | |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for stage, budget in budgets.items():
        now = summary["stages"][stage]
        before = baseline["stages"][stage] if baseline else None
        if before:  # an M3 file can hold -0.0 for "other" (rounding, fixed in M4)
            before = {key: max(0.0, value) for key, value in before.items()}
        old = f"{before['p50']:.2f} | {before['p90']:.2f}" if before else "— | —"
        change = f"{now['p90'] - before['p90']:+.2f}" if before else "—"
        verdict = "OK" if now["p90"] <= budget else "OVER"
        lines.append(f"| {stage} | {budget:g} | {old} | {now['p50']:.2f} | {now['p90']:.2f} | {change} | {verdict} |")
    lines += ["", "| Service | Peak memory MB | Before MB | Limit MB | Peak / limit |", "|---|---|---|---|---|"]
    for name in SERVICES:
        peak = summary["memory_mb"].get(name)
        limit = summary["memory_limit_mb"].get(name)
        before = (baseline or {}).get("memory_mb", {}).get(name)
        lines.append(
            f"| {name} | {f'{peak:.0f}' if peak else '?'} | {f'{before:.0f}' if before else '—'} "
            f"| {f'{limit:.0f}' if limit else 'none'} | {f'{peak / limit:.0%}' if peak and limit else '—'} |"
        )
    ollama = ", ".join(f"{m['name']} {m['gb']} GB" for m in summary["ollama"]) or "not reachable"
    lines += ["", f"Ollama: {ollama}.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", default="own", choices=["own", "fleurs"])
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--compose", action="store_true", help="the services are the docker-compose.yml containers")
    parser.add_argument("--kube", metavar="NAMESPACE", help="the services are the Helm chart's pods in NAMESPACE")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="JSON summary (default out/m3/turns.json)")
    parser.add_argument("--evidence", type=Path, help="also write a Markdown comparison to this file")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_OUT, help="earlier JSON summary to compare with")
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
        # The parts are rounded to 0.01 s each, so the rest can come out as -0.01: there is no negative time.
        t["other"] = max(0.0, round(t["total"] - t.get("stt", 0) - t.get("chat", 0) - t.get("tts", 0), 2))
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
    if args.compose or args.kube:
        probes = probe_containers(args.kube)
        memory = {name: probes[name].get("peak_mb") for name in SERVICES}
        limits = {name: probes[name].get("limit_mb") for name in SERVICES}
        stt_model = probes["stt"].get("stt_model", "?")
        stt_threads = probes["stt"].get("stt_threads", 0)
        chat_model = probes["gateway"].get("chat_model", "?")
    else:
        memory, limits = peak_memory_mb(), dict.fromkeys(SERVICES)
        stt_model, stt_threads, chat_model = settings.stt_model, settings.stt_threads, settings.chat_model
    models = kube_ollama_models(args.kube) if args.kube else ollama_models(settings.openai_base_url)
    if args.kube:
        where = f"minikube pods, namespace {args.kube}, {kube_replicas(args.kube)} stt replica(s)"
    else:
        where = "compose containers" if args.compose else "processes on the laptop"
    summary = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "set": args.set,
        "compose": args.compose,
        "where": where,
        "stt_model": stt_model,
        "stt_threads": stt_threads,
        "chat_model": chat_model,
        "n": len(rows),
        "failed": len(rows) - len(ok),
        "stages": stages,
        "memory_mb": memory,
        "memory_limit_mb": limits,
        "ollama": models,
        "rows": rows,
    }
    print()
    print(f"{len(ok)}/{len(rows)} turns, {stt_model} ({stt_threads} threads) + {chat_model}")
    for stage, s in stages.items():
        print(f"  {stage:6} p50 {s['p50']:5.2f} s  p90 {s['p90']:5.2f} s  max {s['max']:5.2f} s")
    parts = []
    for name in SERVICES:
        text = f"{name} {memory[name]:.0f} MB" if memory[name] else f"{name} not found"
        parts.append(text + (f" of {limits[name]:.0f}" if memory[name] and limits[name] else ""))
    print("  peak memory: " + ", ".join(parts))
    print("  ollama: " + (", ".join(f"{m['name']} {m['gb']} GB" for m in models) or "not reachable"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline.is_file() else None
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {shown(args.out)}")
    if args.evidence:
        write_evidence(args.evidence, summary, baseline, shown(args.baseline))
        print(f"wrote {shown(args.evidence)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
