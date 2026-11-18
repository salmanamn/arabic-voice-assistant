"""Check the four built images against the rules they were designed to (D19, D20), and record what was built.

uv run python scripts/check_images.py [--tag local] [--evidence docs/evidence/m4-images.md]

Per image (voice-stt, voice-tts, voice-gateway, voice-models, tag :local unless --tag; CI builds :ci):
- the configured user is 10001:10001, and a process started in the image really runs with that uid;
- no model file inside: /models is empty and no file anywhere has the name and size of a file in models.lock.json;
- only its own packages: Piper only in tts (GPL, D3), CTranslate2/faster-whisper only in stt, the OpenAI client
  only in gateway, the hub client only in stt (faster-whisper depends on it) and models, pip in none.
Whether the root filesystem is read-only is a property of how a container is started (docker-compose.yml), not of
the image; the runbook checks that on the running containers.
Exit status 1 if any check fails. --evidence writes image ids, sizes and package counts to a Markdown file.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ("stt", "tts", "gateway", "models")
USER = "10001:10001"
# package -> the images allowed to contain it
ONLY_IN = {
    "piper-tts": {"tts"},
    "ctranslate2": {"stt"},
    "faster-whisper": {"stt"},
    "av": {"stt"},
    "openai": {"gateway"},
    "huggingface-hub": {"stt", "models"},
    "pip": set(),
    "uv": set(),
}
# package -> the images that cannot work without it
NEEDED = {
    "faster-whisper": {"stt"},
    "piper-tts": {"tts"},
    "openai": {"gateway"},
    "huggingface-hub": {"models"},
    "uvicorn": {"stt", "tts", "gateway"},
}
# Runs inside each image.
PROBE = """
import importlib.metadata as md, json, os
packages = sorted({d.metadata["Name"].lower().replace("_", "-") for d in md.distributions()})
files = []
for top in ("/app", "/models", "/usr", "/opt", "/home", "/srv", "/var", "/root", "/tmp"):
    for folder, _, names in os.walk(top):
        for name in names:
            path = os.path.join(folder, name)
            if os.path.isfile(path) and not os.path.islink(path):
                files.append([path, os.path.getsize(path)])
venv = sum(size for path, size in files if path.startswith("/app/.venv/"))
print(json.dumps({"uid": os.getuid(), "gid": os.getgid(), "packages": packages, "files": files, "venv": venv,
                  "models_dir": sorted(os.listdir("/models"))}))
"""


def docker(*args: str) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if result.returncode != 0:
        raise SystemExit(f"FAIL docker {' '.join(args[:3])}: {result.stderr.strip().splitlines()[-1:]}")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evidence", type=Path, help="write image ids, sizes and package counts to this file")
    parser.add_argument("--tag", default="local", help="tag of the four images (default local; CI builds ci)")
    args = parser.parse_args()

    lock = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    model_files = {(name, f["size"]) for entry in lock.values() for name, f in entry["files"].items()}
    failures = 0
    rows = []

    def check(image: str, ok: bool, what: str) -> None:
        nonlocal failures
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'} {image:8} {what}")

    for image in IMAGES:
        tag = f"voice-{image}:{args.tag}"
        config = json.loads(docker("image", "inspect", tag))[0]
        inside = json.loads(docker("run", "--rm", "--network", "none", "--entrypoint", "python", tag, "-c", PROBE))
        packages = set(inside["packages"])

        check(
            image, config["Config"].get("User") == USER, f"configured user is {config['Config'].get('User') or 'root'}"
        )
        check(
            image, (inside["uid"], inside["gid"]) == (10001, 10001), f"runs as uid {inside['uid']} gid {inside['gid']}"
        )
        found = [path for path, size in inside["files"] if (Path(path).name, size) in model_files]
        check(
            image,
            not found and not inside["models_dir"],
            f"no model file inside ({len(inside['files'])} files looked at)",
        )
        wrong = sorted(p for p, allowed in ONLY_IN.items() if p in packages and image not in allowed)
        check(image, not wrong, "no package of another image" + (f": has {', '.join(wrong)}" if wrong else ""))
        missing = sorted(p for p, images in NEEDED.items() if image in images and p not in packages)
        check(image, not missing, "has its own packages" + (f": lacks {', '.join(missing)}" if missing else ""))
        rows.append(
            f"| `{tag}` | `{config['Id']}` | {config['Size'] / 1e6:.0f} | {inside['venv'] / 1e6:.0f} "
            f"| {len(packages)} | {config['Config'].get('User')} |"
        )

    print(f"{'IMAGES OK' if not failures else f'{failures} CHECK(S) FAILED'}")
    if args.evidence:
        bases = re.findall(r"^ARG \w+_IMAGE=(\S+)$", (ROOT / "Dockerfile").read_text(encoding="utf-8"), re.MULTILINE)
        engine = docker("version", "--format", "{{.Server.Version}}").strip()
        lines = [
            "# Images built in M4",
            "",
            f"- Date: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}; Docker Engine {engine}; "
            f"`scripts/check_images.py`: {'all checks passed' if not failures else f'{failures} check(s) FAILED'}",
            "- Base images (Dockerfile):",
            *[f"  - `{base}`" for base in bases],
            "",
            "| Image | Image id | Size MB (as Docker reports it) | Of which /app/.venv MB | Python packages | User |",
            "|---|---|---|---|---|---|",
            *rows,
            "",
            "The image id is local: nothing was pushed in M4. The id is the digest a registry will show only when the "
            "engine uses the containerd image store and the image is pushed as it is.",
            "",
        ]
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {args.evidence}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
