"""Text to speech: write a WAV file.

uv run python scripts/say.py "مرحبا بكم" [-o out/say.wav]
"""

import argparse
from pathlib import Path

from voice.settings import load
from voice.tts import TextToSpeech


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text")
    parser.add_argument("-o", "--out", type=Path, default=Path("out/say.wav"))
    args = parser.parse_args()

    speech = TextToSpeech.from_settings(load()).synthesize(args.text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(speech.wav)
    print(
        f"{args.out}: {speech.audio_seconds:.2f} s of audio at {speech.sample_rate} Hz, made in {speech.seconds:.2f} s"
    )


if __name__ == "__main__":
    main()
