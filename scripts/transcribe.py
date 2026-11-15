"""Speech to text: print what an audio file says.

uv run python scripts/transcribe.py out/say.wav [--model stt-turbo]
"""

import argparse
import dataclasses
from pathlib import Path

from voice.settings import load
from voice.stt import SpeechToText


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", help="model directory under models/ (default: STT_MODEL or stt-small)")
    args = parser.parse_args()

    settings = load()
    if args.model:
        settings = dataclasses.replace(settings, stt_model=args.model)
    transcript = SpeechToText.from_settings(settings).transcribe(args.audio)
    print(transcript.text or "(no speech)")
    print(
        f"{settings.stt_model}, {settings.stt_threads} threads: {transcript.audio_seconds:.2f} s of audio "
        f"in {transcript.seconds:.2f} s (RTF {transcript.rtf:.2f})"
    )


if __name__ == "__main__":
    main()
