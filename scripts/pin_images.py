"""Pin every image this repository pulls to a digest, so a tag that moves cannot change what is built or run (D19).

uv run python scripts/pin_images.py            ask the registries for each tag's digest and write tag@sha256:... back
uv run python scripts/pin_images.py --check    no network: exit 1 if an image is not pinned

Two kinds of line are handled: `ARG <NAME>_IMAGE=<image>` in Dockerfile (the base images) and `image: <image>`
in docker-compose.yml. Images tagged `:local` are the ones this repository builds; they are left alone.
Run it again to move to the newest digest of the same tags, then rebuild and scan before committing.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "Dockerfile": re.compile(r"^(ARG \w+_IMAGE=)(\S+)$", re.MULTILINE),
    "docker-compose.yml": re.compile(r"^(\s*image: )(\S+)", re.MULTILINE),
}
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def split(reference: str) -> tuple[str, str]:
    """'repo:tag@sha256:...' -> ('repo:tag', 'sha256:...'); the digest is '' when there is none."""
    tagged, _, digest = reference.partition("@")
    return tagged, digest


def resolve(tagged: str) -> str:
    """The digest the registry serves for a tag right now (the multi-platform index when there is one)."""
    result = subprocess.run(  # noqa: S603 (fixed command; the image names come from this repository's own files)
        ["docker", "buildx", "imagetools", "inspect", tagged, "--format", "{{.Manifest.Digest}}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    digest = result.stdout.strip()
    if result.returncode != 0 or not DIGEST.match(digest):
        lines = (result.stderr or result.stdout).strip().splitlines()
        raise SystemExit(f"FAIL {tagged}: {lines[-1] if lines else 'no digest returned'}")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only check that every image is pinned")
    args = parser.parse_args()

    unpinned = 0
    for name, pattern in FILES.items():
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            tagged, old = split(match.group(2))
            if tagged.endswith(":local"):
                continue
            if args.check:
                state = "pinned" if DIGEST.match(old) else "NOT PINNED"
                unpinned += state != "pinned"
                print(f"{state:10} {name}: {tagged} {old[:19]}")
                continue
            new = resolve(tagged)
            state = "unchanged" if new == old else ("moved" if old else "pinned")
            print(f"{state:10} {name}: {tagged}@{new}")
            text = text.replace(match.group(0), f"{match.group(1)}{tagged}@{new}", 1)
        if not args.check:
            path.write_text(text, encoding="utf-8")
    if unpinned:
        print(f"{unpinned} image(s) not pinned: run scripts/pin_images.py")
    return 1 if unpinned else 0


if __name__ == "__main__":
    sys.exit(main())
