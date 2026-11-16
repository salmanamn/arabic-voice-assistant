"""How the compose services stop (M5, D31): seconds from SIGTERM to exit, the exit code, and uvicorn's shutdown lines.

uv run python scripts/check_stop.py [--label TEXT] [--evidence FILE]

Needs the compose stack running. Watches `docker events` while `docker compose stop` runs, then reports for each
container: the seconds from Docker's first kill (SIGTERM) to the container's exit, the exit code (0: it stopped by
itself; 137: killed when the grace period ran out) and the shutdown lines of its log with their timestamps. Those
show where a slow stop spent its time: after "Waiting for connections to close" on requests still open, after
"Waiting for application shutdown" on releasing the model, after "Finished server process" in the interpreter's
own exit. --evidence appends a section to FILE (created if missing). Exit 1 when any container was killed.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT = "voice-lab"
CONTAINERS = ("voice-gateway", "voice-stt", "voice-tts", "voice-ollama")
PHASES = ("Shutting down", "Waiting for", "Application shutdown", "Finished server process")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", default="", help="what is being stopped, for the evidence heading")
    parser.add_argument("--evidence", type=Path, help="append the result as Markdown to this file")
    args = parser.parse_args()

    running = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    targets = [name for name in CONTAINERS if name in running]
    if not targets:
        print("FAIL no voice-lab container is running (docker compose up -d --wait first)")
        return 1
    since = datetime.now(UTC)
    events = subprocess.Popen(  # noqa: S603
        [  # noqa: S607
            "docker",
            "events",
            "--filter",
            "type=container",
            "--filter",
            f"label=com.docker.compose.project={PROJECT}",
            "--format",
            "{{json .}}",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    time.sleep(1)  # docker events only reports what happens after it has started
    started = time.monotonic()
    subprocess.run(["docker", "compose", "stop"], capture_output=True, check=False)  # noqa: S607
    took = time.monotonic() - started
    time.sleep(1)
    events.terminate()
    out, _ = events.communicate(timeout=10)

    kill_at: dict[str, int] = {}
    died: dict[str, tuple[int, str]] = {}
    for line in out.splitlines():
        event = json.loads(line)
        name = event.get("Actor", {}).get("Attributes", {}).get("name", "")
        if event.get("Action") == "kill":
            kill_at.setdefault(name, event["timeNano"])
        elif event.get("Action") == "die":
            died[name] = (event["timeNano"], event["Actor"]["Attributes"].get("exitCode", "?"))

    rows, killed = [], 0
    for name in targets:
        first, (end, code) = kill_at.get(name), died.get(name, (None, "?"))
        seconds = f"{(end - first) / 1e9:.1f}" if first and end else "?"
        killed += code == "137"
        log = subprocess.run(  # noqa: S603
            ["docker", "logs", "-t", "--since", since.isoformat(), name],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        lines = [
            f"{stamp[11:23]} {text.strip()}"
            for stamp, _, text in (entry.partition(" ") for entry in (log.stdout + log.stderr).splitlines())
            if any(phase in text for phase in PHASES)
        ]
        rows.append((name, seconds, code, lines))
        print(f"{name:14} stopped in {seconds:>5} s  exit {code}")
        for entry in lines:
            print(f"    {entry}")
    print(f"docker compose stop took {took:.1f} s; {killed} container(s) killed")

    if args.evidence:
        section = [
            f"## {args.label or 'docker compose stop'} ({since:%Y-%m-%d %H:%M} UTC)",
            "",
            "| Container | SIGTERM to exit, s | Exit code |",
            "|---|---|---|",
            *[f"| {name} | {seconds} | {code} |" for name, seconds, code, _ in rows],
            "",
        ]
        for name, _, _, lines in rows:
            if lines:
                section += [f"`{name}`:", "```", *lines, "```", ""]
        heading = [] if args.evidence.is_file() else ["# How the services stop (M5, D31)", ""]
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        with args.evidence.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(heading + section) + "\n")
        print(f"appended to {args.evidence}")
    return 1 if killed else 0


if __name__ == "__main__":
    sys.exit(main())
