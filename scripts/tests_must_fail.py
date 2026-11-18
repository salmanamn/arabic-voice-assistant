"""Tests must fail: apply known-bad changes one at a time and require the unit tests to catch each one.

Each mutation breaks one property the project depends on: only locked model bytes, a read-only check that changes
nothing, downloads that resume, one model call at a time with a bounded queue, input limits, errors and logs that
never echo what was said, a new connection per speech call, threads from physical cores, the request shape for
reasoning models, text cleaned before it is spoken. The script works on a temporary copy of the repository, so the
working tree is never changed. Exit 1 when a mutation survives (the tests still pass), when its anchor text is no
longer in the code (update the mutation together with the code), or when the clean copy fails (D35).

Usage: uv run python scripts/tests_must_fail.py [--only NAME] [--list]
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPY = ("src", "tests", "eval", "pyproject.toml", "models.lock.json")
SUMMARY = re.compile(r"(\d+) failed")


@dataclass(frozen=True)
class Mutation:
    name: str
    file: str
    old: str
    new: str
    tests: str  # pytest target that must fail


MUTATIONS = [
    Mutation(
        "locked-fetch-asks-for-newest",
        "src/voice/modelstore.py",
        'revision = locked["revision"] if locked else hub.resolve_revision(spec.repo)',
        "revision = hub.resolve_revision(spec.repo)",
        "tests/unit/test_fetch_job.py",
    ),
    Mutation(
        "changed-file-accepted",
        "src/voice/modelstore.py",
        "        elif actual != expected:",
        "        elif False:",
        "tests/unit/test_modelstore.py",
    ),
    Mutation(
        "extra-files-kept",
        "src/voice/fetch_job.py",
        '            if item.is_file() and item.name not in entry["files"]:',
        "            if False:",
        "tests/unit/test_fetch_job.py",
    ),
    Mutation(
        "check-mode-downloads",
        "src/voice/fetch_job.py",
        'if names[:1] == ["--check"]:',
        "if False:",
        "tests/unit/test_fetch_job.py",
    ),
    Mutation(
        "download-restarts-from-zero",
        "src/voice/download.py",
        'headers["Range"] = f"bytes={have}-"',
        "pass",
        "tests/unit/test_download.py",
    ),
    Mutation(
        "download-gives-up-at-once",
        "src/voice/download.py",
        "stalls = 0 if wrote else stalls + 1",
        "stalls = max_stalls",
        "tests/unit/test_download.py",
    ),
    Mutation(
        "missing-file-retried",
        "src/voice/download.py",
        'if isinstance(exc, DownloadError) and "from the model host" in str(exc):',
        "if False:",
        "tests/unit/test_download.py",
    ),
    Mutation(
        "unbounded-queue",
        "src/voice/services/common.py",
        "if self._lock.locked() and self.waiting >= self.max_waiting:",
        "if False:",
        "tests/unit/test_speech_services.py",
    ),
    Mutation(
        "upload-limit-off",
        "src/voice/services/stt_app.py",
        "        if len(data) > settings.max_upload_bytes:",
        "        if False:",
        "tests/unit/test_speech_services.py",
    ),
    Mutation(
        "audio-length-unchecked",
        "src/voice/services/stt_app.py",
        "    if seconds > max_seconds:",
        "    if False:",
        "tests/unit/test_speech_services.py",
    ),
    Mutation(
        "validation-echoes-input",
        "src/voice/services/common.py",
        "    @app.exception_handler(RequestValidationError)\n",
        "",
        "tests/unit/test_speech_services.py",
    ),
    Mutation(
        "log-carries-the-words",
        "src/voice/services/gateway_app.py",
        'log.info("turn: heard %d chars, answered %d chars, %s", len(heard), len(answer), result)',
        'log.info("turn: heard %s, answered %s, %s", heard, answer, result)',
        "tests/unit/test_gateway.py",
    ),
    Mutation(
        "speech-connections-kept-alive",
        "src/voice/services/gateway_app.py",
        "max_keepalive_connections=0",
        "max_keepalive_connections=20",
        "tests/unit/test_gateway.py",
    ),
    Mutation(
        "answer-not-cut",
        "src/voice/services/gateway_app.py",
        "    if len(text) <= limit:",
        "    if True:",
        "tests/unit/test_gateway.py",
    ),
    Mutation(
        "markdown-spoken",
        "src/voice/textnorm.py",
        '    text = _EMPHASIS.sub("", text)',
        "    pass",
        "tests/unit/test_textnorm.py",
    ),
    Mutation(
        "hyperthreads-counted",
        "src/voice/settings.py",
        'for name in ("core_cpus_list", "thread_siblings_list"):',
        "for name in ():",
        "tests/unit/test_settings.py",
    ),
    Mutation(
        "reasoning-model-gets-temperature",
        "src/voice/llm.py",
        'if self.reasoning_effort and self.reasoning_effort != "none":',
        "if False:",
        "tests/unit/test_llm.py",
    ),
]


def make_copy(dest: Path) -> None:
    ignore = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")
    for name in COPY:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, dest / name, ignore=ignore)
        else:
            shutil.copy2(src, dest / name)


def pytest(cwd: Path, target: str) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target]
    # The project is installed in the venv as an editable package pointing at the real src/: put the copy first.
    env = {**os.environ, "PYTHONPATH": str(cwd / "src")}
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)  # noqa: S603
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return proc.returncode, lines[-1] if lines else proc.stderr.strip()[-200:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="run a single mutation by name")
    parser.add_argument("--list", action="store_true", help="list the mutations and exit")
    args = parser.parse_args()
    mutations = [m for m in MUTATIONS if not args.only or m.name == args.only]
    if args.list or not mutations:
        for m in MUTATIONS:
            print(f"{m.name:34} {m.file}")
        return 0 if args.list else 2

    with tempfile.TemporaryDirectory(prefix="tests-must-fail-") as tmp:
        work = Path(tmp)
        make_copy(work)
        code, summary = pytest(work, "tests/unit")
        if code != 0:
            print(f"ERROR    baseline: unit tests fail on the unmodified copy ({summary})")
            return 1
        print(f"OK       baseline: {summary}")

        problems = 0
        for m in mutations:
            path = work / m.file
            original = path.read_text()
            if original.count(m.old) != 1:
                print(f"STALE    {m.name:34} anchor found {original.count(m.old)}x in {m.file}; update the mutation")
                problems += 1
                continue
            path.write_text(original.replace(m.old, m.new))
            try:
                code, summary = pytest(work, m.tests)
            finally:
                path.write_text(original)
            if code == 1 and SUMMARY.search(summary):
                print(f"KILLED   {m.name:34} {m.tests} ({SUMMARY.search(summary).group(0)})")
            elif code == 0:
                print(f"SURVIVED {m.name:34} {m.tests} still passes: add a test for this behaviour")
                problems += 1
            else:
                print(f"ERROR    {m.name:34} pytest exit {code} (not a test failure): {summary}")
                problems += 1

    killed = len(mutations) - problems
    print(f"{killed}/{len(mutations)} mutations killed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
