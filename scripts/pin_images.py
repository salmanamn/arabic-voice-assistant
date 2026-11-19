"""Pin every image this repository pulls to a digest, so a tag that moves cannot change what is built or run (D19).

uv run python scripts/pin_images.py                 ask the registries for each tag's digest and write it back
uv run python scripts/pin_images.py --only REPO     the same for one repository (e.g. floci/floci-az), nothing else
uv run python scripts/pin_images.py --check         no network: exit 1 if an image is not pinned

Four kinds of line are handled: `ARG <NAME>_IMAGE=<image>` in Dockerfile (the base images), `image: <image>` in
docker-compose.yml and in the CI workflow's service containers, and the `ollama:` image in the chart's values.yaml.
Images tagged `:local` are the ones this repository builds; they are left alone. --check also fails when two files
pin different references of the same repository (compose and the chart for Ollama, compose and CI for floci-az).
CI runs the resolving mode weekly and fails when a tag has moved (D36): the stand-in for Dependabot, which does not
read `ARG` defaults.
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
    "deploy/charts/voice/values.yaml": re.compile(r"^(  ollama: )(\S+)$", re.MULTILINE),
    ".github/workflows/ci.yml": re.compile(r"^(\s+image: )(\S+)", re.MULTILINE),
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
    parser.add_argument("--only", metavar="REPO", help="resolve only this repository (e.g. floci/floci-az)")
    args = parser.parse_args()

    unpinned = 0
    seen: dict[str, set[str]] = {}
    for name, pattern in FILES.items():
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            tagged, old = split(match.group(2))
            if tagged.endswith(":local"):
                continue
            if args.only and tagged.split(":")[0] != args.only:
                seen.setdefault(tagged.split(":")[0], set()).add(match.group(2))
                continue
            if args.check:
                seen.setdefault(tagged.split(":")[0], set()).add(match.group(2))
                state = "pinned" if DIGEST.match(old) else "NOT PINNED"
                unpinned += state != "pinned"
                print(f"{state:10} {name}: {tagged} {old[:19]}")
                continue
            new = resolve(tagged)
            seen.setdefault(tagged.split(":")[0], set()).add(f"{tagged}@{new}")  # what the file holds after this run
            state = "unchanged" if new == old else ("moved" if old else "pinned")
            print(f"{state:10} {name}: {tagged}@{new}")
            text = text.replace(match.group(0), f"{match.group(1)}{tagged}@{new}", 1)
        if not args.check:
            path.write_text(text, encoding="utf-8")
    if unpinned:
        print(f"{unpinned} image(s) not pinned: run scripts/pin_images.py")
    differ = {repo: refs for repo, refs in seen.items() if len(refs) > 1}
    for repo, refs in differ.items():
        print(f"DIFFERENT  {repo} is pinned to {len(refs)} different references: {', '.join(sorted(refs))}")
    return 1 if unpinned or (args.check and differ) else 0


if __name__ == "__main__":
    sys.exit(main())
