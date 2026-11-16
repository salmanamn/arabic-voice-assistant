"""Real-speech test sets (D15). Audio stays out of git under data/speech/<set>/; each set has a manifest.jsonl
there with one line per utterance: id, file (relative to the set directory), reference text, seconds, sha256, style.

- own:    your recordings of the prompts in eval/speech/own.jsonl (the product's case: short questions, one speaker,
          your microphone). Imported from the newest files in a folder, in recording order.
- fleurs: the first N sentences of Google's FLEURS Arabic (ar_eg) test split: read speech, one recording per
          sentence, rotating over each sentence's speakers, CC BY 4.0. The archive is untrusted input: only the selected
          .wav members are read, by name, and written under names we choose.
"""

import hashlib
import json
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path

MANIFEST = "manifest.jsonl"
FLEURS_REPO = "google/fleurs"
FLEURS_LANG = "ar_eg"
FLEURS_RATE = 16000  # FLEURS audio is 16 kHz; num_samples / rate = seconds


@dataclass(frozen=True)
class Utterance:
    id: str
    file: str
    text: str
    seconds: float
    sha256: str
    style: str = "msa"  # msa | gulf (own set); fleurs is msa read speech


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_manifest(directory: Path) -> list[Utterance]:
    path = directory / MANIFEST
    if not path.is_file():
        raise FileNotFoundError(f"{path} does not exist (run scripts/speech_set.py first)")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Utterance(**json.loads(line)) for line in lines if line.strip()]


def write_manifest(directory: Path, utterances: list[Utterance]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(u), ensure_ascii=False) for u in sorted(utterances, key=lambda u: u.id)]
    (directory / MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_prompts(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


AUDIO_SUFFIXES = {".m4a", ".wav", ".mp3", ".ogg", ".webm", ".flac", ".aac", ".wma"}


def newest_recordings(folder: Path, count: int) -> list[Path]:
    """The `count` most recently modified audio files in `folder`, oldest first (= the order they were recorded)."""
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES]
    if len(files) < count:
        raise ValueError(f"{folder} has {len(files)} audio files, {count} needed")
    newest = sorted(files, key=lambda p: p.stat().st_mtime)[-count:]
    return newest


def select_fleurs(tsv: str, count: int, max_seconds: float) -> list[dict]:
    """Rows of a FLEURS split TSV -> one recording each of the first `count` distinct sentences (lowest sentence id
    first) that have a recording of at most `max_seconds`. Columns: id, file_name, raw_transcription, transcription,
    characters, num_samples, gender.

    FLEURS collected each sentence from three different native speakers and kept between zero and three of those
    recordings. The TSV names no speaker, and its gender column is no help either (ar_eg test: FEMALE on all 428
    rows). To spread the set over speakers, the n-th selected sentence takes its (n mod k)-th usable recording, in
    file order, where k is how many it has. Every row carries `take` (0-based position among the usable ones).
    """
    by_sentence: dict[int, list[dict]] = {}
    for line in tsv.splitlines():
        cols = line.split("\t")
        if len(cols) < 7 or not cols[0].isdigit():
            continue
        seconds = int(cols[5]) / FLEURS_RATE
        if seconds > max_seconds:
            continue
        by_sentence.setdefault(int(cols[0]), []).append(
            {
                "sentence": int(cols[0]),
                "file_name": cols[1],
                "text": cols[2],
                "seconds": seconds,
                "gender": cols[6].strip().upper(),
            }
        )
    rows = []
    for n, (_, recordings) in enumerate(sorted(by_sentence.items())[:count]):
        take = n % len(recordings)
        rows.append({**recordings[take], "take": take})
    return rows


def extract_members(archive: Path, wanted: dict[str, Path]) -> set[str]:
    """Copy archive members whose base name is a key of `wanted` (regular files only) to the mapped path.
    Nothing else in the archive is touched; member paths are never used as output paths. Returns names not found."""
    missing = set(wanted)
    with tarfile.open(archive) as tar:
        for member in tar:
            name = Path(member.name).name
            if name not in missing or not member.isfile():
                continue
            source = tar.extractfile(member)
            if source is None:
                continue
            wanted[name].parent.mkdir(parents=True, exist_ok=True)
            wanted[name].write_bytes(source.read())
            missing.discard(name)
            if not missing:
                break
    return missing
