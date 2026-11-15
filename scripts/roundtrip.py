"""Round trip: every sentence in eval/roundtrip.jsonl goes text -> Piper -> WAV -> faster-whisper -> text.

It proves that both models load and work together and gives a first speed measurement on this machine.
It is NOT a speech-recognition quality measure: the audio is one clean synthetic voice (D8).

uv run python scripts/roundtrip.py [--model stt-turbo] [--out docs/evidence/m1-roundtrip-small.md]
"""

import argparse
import dataclasses
import io
import json
import platform
import statistics
import sys
import wave
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import onnxruntime

from voice.modelstore import LOCK_FILE, read_lock
from voice.settings import load
from voice.stt import SpeechToText
from voice.textnorm import score, total
from voice.tts import TextToSpeech

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "eval" / "roundtrip.jsonl"
AUDIO_DIR = ROOT / "out" / "roundtrip"

# Gates. Clean synthetic speech is the easy case, so these are loose "the pipeline works" limits (D8).
# Measured when the gates were set: Whisper small 3.3 % CER, 8 % WER (passes); Whisper tiny 6.5 %, 30 % (fails on WER).
MAX_CORPUS_CER = 0.10
MAX_CORPUS_WER = 0.20
MAX_SENTENCE_CER = 0.30


def cpu_model() -> str:
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown CPU"


def silence_wav(seconds: float = 2.0, rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        wav_file.writeframes(b"\x00\x00" * int(seconds * rate))
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--model", help="speech-to-text model directory under models/ (default: STT_MODEL or stt-small)"
    )
    parser.add_argument("--out", type=Path, help="also write the result as a markdown evidence file")
    args = parser.parse_args()

    settings = load()
    if args.model:
        settings = dataclasses.replace(settings, stt_model=args.model)
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]

    onnxruntime.set_seed(0)  # Piper adds random noise; a fixed seed gives the same audio on every run on this machine
    tts = TextToSpeech.from_settings(settings)
    stt = SpeechToText.from_settings(settings)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for case in cases:
        speech = tts.synthesize(case["text"])
        wav_path = AUDIO_DIR / f"{case['id']}.wav"
        wav_path.write_bytes(speech.wav)
        transcript = stt.transcribe(wav_path)
        result = score(case["text"], transcript.text)
        rows.append({"case": case, "speech": speech, "transcript": transcript, "score": result})
        print(
            f"{case['id']}  CER {result.cer:6.1%}  WER {result.wer:6.1%}  audio {speech.audio_seconds:5.2f} s  "
            f"tts {speech.seconds:5.2f} s  stt {transcript.seconds:5.2f} s  | {transcript.text}"
        )

    silence_path = AUDIO_DIR / "silence.wav"
    silence_path.write_bytes(silence_wav())
    silence = stt.transcribe(silence_path)

    corpus = total(row["score"] for row in rows)
    worst = max(rows, key=lambda row: row["score"].cer)
    audio_seconds = sum(row["speech"].audio_seconds for row in rows)
    stt_seconds = [row["transcript"].seconds for row in rows]
    tts_rtf = sum(row["speech"].seconds for row in rows) / audio_seconds
    stt_rtf = sum(stt_seconds) / audio_seconds
    checks = [
        (f"corpus CER {corpus.cer:.1%} <= {MAX_CORPUS_CER:.0%}", corpus.cer <= MAX_CORPUS_CER),
        (f"corpus WER {corpus.wer:.1%} <= {MAX_CORPUS_WER:.0%}", corpus.wer <= MAX_CORPUS_WER),
        (
            f"worst sentence {worst['case']['id']} CER {worst['score'].cer:.1%} <= {MAX_SENTENCE_CER:.0%}",
            worst["score"].cer <= MAX_SENTENCE_CER,
        ),
        (f"2 s of silence -> {silence.text!r} (must be empty)", silence.text == ""),
    ]
    summary = [
        f"sentences {len(rows)}, audio {audio_seconds:.1f} s, corpus CER {corpus.cer:.1%}, corpus WER {corpus.wer:.1%}",
        f"speech to text: median {statistics.median(stt_seconds):.2f} s, slowest {max(stt_seconds):.2f} s "
        f"per sentence, RTF {stt_rtf:.2f}",
        f"text to speech: RTF {tts_rtf:.2f}",
    ]
    print()
    print("\n".join(summary))
    for label, passed in checks:
        print(f"{'OK  ' if passed else 'FAIL'} {label}")
    passed = all(ok for _, ok in checks)
    print("ROUND TRIP PASSED" if passed else "ROUND TRIP FAILED")

    if args.out:
        lock = read_lock(ROOT / LOCK_FILE)
        revision = {
            name: lock.get(name, {}).get("revision", "not locked")[:12]
            for name in (settings.stt_model, settings.tts_voice)
        }
        lines = [
            f"# Round trip: Piper -> faster-whisper ({settings.stt_model})",
            "",
            f"- Date: {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
            f"- Machine: {cpu_model()}, {settings.stt_threads} threads for speech to text",
            f"- Speech to text: `{settings.stt_model}` @ `{revision[settings.stt_model]}`, "
            f"compute type {settings.stt_compute_type}, beam {settings.stt_beam_size}, language `{settings.language}`, "
            f"faster-whisper {version('faster-whisper')}, ctranslate2 {version('ctranslate2')}",
            f"- Text to speech: `{settings.tts_voice}` @ `{revision[settings.tts_voice]}`, "
            f"piper-tts {version('piper-tts')}, onnxruntime {version('onnxruntime')}",
            "- Synthetic audio from one voice: this checks the pipeline and its speed, not recognition quality.",
            "",
            "| Id | CER | WER | Audio s | TTS s | STT s | Reference | Heard |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in rows:
            speech, transcript, result = row["speech"], row["transcript"], row["score"]
            lines.append(
                f"| {row['case']['id']} | {result.cer:.1%} | {result.wer:.1%} | {speech.audio_seconds:.2f} "
                f"| {speech.seconds:.2f} | {transcript.seconds:.2f} | {row['case']['text']} | {transcript.text} |"
            )
        lines += ["", *[f"- {line}" for line in summary]]
        lines += [f"- {'OK' if ok else 'FAIL'}: {label}" for label, ok in checks]
        lines += ["", f"**{'PASSED' if passed else 'FAILED'}**", ""]
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
