"""Build the real-speech test sets under data/speech/ (gitignored; see src/voice/speechset.py and D15).

uv run python scripts/speech_set.py own FOLDER            the newest 20 recordings in FOLDER, oldest first = S01..S20
uv run python scripts/speech_set.py own --id S07 FILE     replace one recording
uv run python scripts/speech_set.py fleurs [--count 40]   FLEURS Arabic test sentences (downloads about 300 MB once)
uv run python scripts/speech_set.py status                what is on disk
"""

import argparse
import shutil
import sys
from pathlib import Path

from voice.speechset import (
    FLEURS_LANG,
    FLEURS_REPO,
    Utterance,
    extract_members,
    newest_recordings,
    read_manifest,
    read_prompts,
    select_fleurs,
    sha256_bytes,
    write_manifest,
)
from voice.stt import SAMPLE_RATE, SpeechToText

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "speech"
PROMPTS = ROOT / "eval" / "speech" / "own.jsonl"
MAX_SECONDS = 20.0  # the services refuse longer audio (MAX_AUDIO_SECONDS)


def seconds_of(path: Path) -> float:
    return len(SpeechToText.decode(path)) / SAMPLE_RATE  # also proves FFmpeg can read the file


def import_own(sources: list[tuple[dict, Path]]) -> None:
    directory = DATA / "own"
    try:
        existing = {u.id: u for u in read_manifest(directory)}
    except FileNotFoundError:
        existing = {}
    for prompt, source in sources:
        target = directory / f"{prompt['id']}{source.suffix.lower()}"
        for old in directory.glob(f"{prompt['id']}.*"):
            old.unlink()  # a re-recording may have another format
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        seconds = seconds_of(target)
        existing[prompt["id"]] = Utterance(
            id=prompt["id"],
            file=target.name,
            text=prompt["text"],
            seconds=round(seconds, 2),
            sha256=sha256_bytes(target.read_bytes()),
            style=prompt.get("style", "msa"),
        )
        flag = "" if 0.5 <= seconds <= MAX_SECONDS else "   <-- check this one"
        print(f"{prompt['id']}  {seconds:5.1f} s  {source.name:28.28}  {prompt['text']}{flag}")
    write_manifest(directory, list(existing.values()))
    print(f"{len(existing)}/{len(read_prompts(PROMPTS))} recordings in {directory.relative_to(ROOT)}")


def build_fleurs(count: int) -> None:
    from huggingface_hub import HfApi, hf_hub_download  # only this step needs the hub client

    directory = DATA / "fleurs"
    downloads = ROOT / "data" / "downloads" / "fleurs"
    revision = HfApi().dataset_info(FLEURS_REPO).sha
    print(f"{FLEURS_REPO} @ {revision[:12]}")
    tsv = hf_hub_download(
        FLEURS_REPO, f"data/{FLEURS_LANG}/test.tsv", repo_type="dataset", revision=revision, local_dir=downloads
    )
    rows = select_fleurs(Path(tsv).read_text(encoding="utf-8"), count, MAX_SECONDS)
    if len(rows) < count:
        raise SystemExit(f"only {len(rows)} sentences of at most {MAX_SECONDS:g} s in the test split")
    archive = hf_hub_download(
        FLEURS_REPO,
        f"data/{FLEURS_LANG}/audio/test.tar.gz",
        repo_type="dataset",
        revision=revision,
        local_dir=downloads,
    )
    names = {row["file_name"]: directory / f"F{n:03d}.wav" for n, row in enumerate(rows, start=1)}
    missing = extract_members(Path(archive), names)
    if missing:
        raise SystemExit(f"not in the archive: {', '.join(sorted(missing))}")
    utterances = []
    for n, row in enumerate(rows, start=1):
        path = names[row["file_name"]]
        utterances.append(
            Utterance(
                id=f"F{n:03d}",
                file=path.name,
                text=row["text"],
                seconds=round(row["seconds"], 2),
                sha256=sha256_bytes(path.read_bytes()),
                style=f"fleurs-{row['gender'].lower()}",
            )
        )
    write_manifest(directory, utterances)
    (directory / "SOURCE").write_text(
        f"{FLEURS_REPO} @ {revision}, data/{FLEURS_LANG} test split, first {count} sentences of at most "
        f"{MAX_SECONDS:g} s (one recording each). Licence: CC BY 4.0. Conneau et al., FLEURS (2022).\n",
        encoding="utf-8",
    )
    total = sum(u.seconds for u in utterances)
    print(f"{len(utterances)} sentences, {total / 60:.1f} min of audio in {directory.relative_to(ROOT)}")


def status() -> None:
    for name in ("own", "fleurs"):
        try:
            utterances = read_manifest(DATA / name)
        except FileNotFoundError:
            print(f"{name:7} not built")
            continue
        missing = [u.id for u in utterances if not (DATA / name / u.file).is_file()]
        changed = [
            u.id
            for u in utterances
            if u.id not in missing and sha256_bytes((DATA / name / u.file).read_bytes()) != u.sha256
        ]
        total = sum(u.seconds for u in utterances)
        state = "ok" if not missing and not changed else f"missing {missing} changed {changed}"
        print(f"{name:7} {len(utterances):3} utterances, {total / 60:4.1f} min  {state}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    own = sub.add_parser("own", help="import your recordings")
    own.add_argument("path", type=Path, help="folder with the recordings, or one file with --id")
    own.add_argument("--id", help="replace one recording, e.g. S07")
    fleurs = sub.add_parser("fleurs", help="download FLEURS Arabic test sentences")
    fleurs.add_argument("--count", type=int, default=40)
    sub.add_parser("status")
    args = parser.parse_args()

    if args.command == "status":
        status()
    elif args.command == "fleurs":
        build_fleurs(args.count)
    elif args.id:
        prompts = {p["id"]: p for p in read_prompts(PROMPTS)}
        if args.id not in prompts or not args.path.is_file():
            parser.error(f"--id must be one of {', '.join(prompts)} and PATH a file")
        import_own([(prompts[args.id], args.path)])
    else:
        prompts = read_prompts(PROMPTS)
        import_own(list(zip(prompts, newest_recordings(args.path, len(prompts)), strict=True)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
