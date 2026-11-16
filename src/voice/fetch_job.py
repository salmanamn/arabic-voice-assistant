"""Model-fetch job: put exactly the locked model files into MODELS_DIR, or fail.

python -m voice.fetch_job NAME [NAME ...]

Runs to completion before the speech services start: a one-shot service in compose, an init container on
Kubernetes (D20). It is the only component that talks to the model host and the only one that writes the models
volume; the services mount that volume read-only.

For each NAME the job
- refuses a model that is not in the lock (it never resolves "the newest revision" and never writes the lock);
- removes files in the model's directory that the lock does not list (left over from another revision);
- does nothing more when the directory already matches the lock: no network is needed for a start on a warm volume;
- otherwise downloads the locked revision and compares the SHA-256 and size of every file with the lock.
Exit status 0 only when every requested model is exactly the locked one.

Environment: MODELS_DIR (where to), MODELS_LOCK (the lock file, default ./models.lock.json), HF_ENDPOINT
(another model host or a mirror; read by the hub client). The hub client keeps its own small cache; unless HF_HOME
says otherwise it goes to MODELS_DIR/.hf, on disk and not in the container's memory-backed /tmp, and is removed
at the end.
"""

import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from voice.modelstore import CATALOG, LOCK_FILE, Hub, HuggingFaceHub, IntegrityError, fetch, read_lock, verify
from voice.settings import load


def ensure(name: str, models_dir: Path, lock: dict, hub_factory: Callable[[], Hub]) -> tuple[bool, str]:
    """Make models_dir/<name> exactly the locked model. Returns (ok, one line for the log)."""
    if name not in CATALOG:
        return False, f"{name}: not in the catalog ({', '.join(CATALOG)})"
    entry = lock.get(name)
    if entry is None:
        return False, f"{name}: not in {LOCK_FILE}; lock it on a workstation first (scripts/fetch_models.py)"
    megabytes = sum(f["size"] for f in entry["files"].values()) / 1e6
    what = f"{len(entry['files'])} files, {megabytes:.0f} MB"

    directory = models_dir / name
    removed = []
    if directory.is_dir():
        for item in sorted(directory.iterdir()):
            if item.is_file() and item.name not in entry["files"]:
                item.unlink()
                removed.append(item.name)
    note = f" (removed {', '.join(removed)}: not in the lock)" if removed else ""
    if not verify(name, models_dir, lock):
        return True, f"{name}: {what}, already in {directory}{note}"

    try:
        fetch(name, models_dir, dict(lock), hub_factory())  # a copy: fetch() stores its result in the lock it is given
    except IntegrityError as exc:
        return False, str(exc)
    except Exception as exc:  # network errors, a missing revision, a full disk: one line, no traceback
        return False, f"{name}: download failed ({type(exc).__name__}: {exc})"
    problems = verify(name, models_dir, lock)
    if problems:
        return False, "; ".join(problems)
    return True, f"{name}: {entry['repo']} @ {entry['revision'][:12]}, {what}, downloaded and verified{note}"


def run(names: list[str], models_dir: Path, lock_path: Path, hub_factory: Callable[[], Hub]) -> int:
    if not names:
        print("FAIL no model named: python -m voice.fetch_job NAME [NAME ...]")
        return 1
    if not lock_path.is_file():
        print(f"FAIL {lock_path} does not exist")
        return 1
    lock = read_lock(lock_path)
    models_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name in names:
        ok, line = ensure(name, models_dir, lock, hub_factory)
        failed += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {line}", flush=True)
    print(f"{len(names) - failed}/{len(names)} models match {lock_path.name}", flush=True)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    names = sys.argv[1:] if argv is None else argv
    models_dir = load().models_dir
    lock_path = Path(os.environ.get("MODELS_LOCK", LOCK_FILE))
    hub_home = models_dir / ".hf"
    os.environ.setdefault("HF_HOME", str(hub_home))  # before the hub client is imported (HuggingFaceHub())
    try:
        return run(names, models_dir, lock_path, HuggingFaceHub)
    finally:
        shutil.rmtree(hub_home, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
