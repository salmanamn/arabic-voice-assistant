"""Text to speech: Piper (VITS voice on ONNX Runtime), CPU. Arabic text is diacritized by Piper itself
(libtashkeel model inside the piper-tts package) before it is turned into phonemes."""

import io
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from voice.settings import Settings
from voice.textnorm import clean_for_speech


@dataclass(frozen=True)
class Speech:
    wav: bytes  # a complete WAV file: 16-bit PCM, mono, at the voice's sample rate
    sample_rate: int
    audio_seconds: float
    seconds: float  # wall time of the synthesis

    @property
    def rtf(self) -> float:
        return self.seconds / self.audio_seconds if self.audio_seconds else 0.0


class TextToSpeech:
    def __init__(self, voice_dir: Path) -> None:
        from piper import PiperVoice  # imported here: only the text-to-speech side needs Piper

        models = sorted(voice_dir.glob("*.onnx"))
        if len(models) != 1 or not Path(f"{models[0]}.json").is_file():
            raise FileNotFoundError(
                f"{voice_dir}: expected one .onnx with its .onnx.json (run scripts/fetch_models.py)"
            )
        self._voice = PiperVoice.load(models[0])
        self.sample_rate = self._voice.config.sample_rate

    @classmethod
    def from_settings(cls, settings: Settings) -> "TextToSpeech":
        return cls(settings.tts_voice_dir)

    def synthesize(self, text: str) -> Speech:
        text = clean_for_speech(text)
        if not text:
            raise ValueError("nothing to say")
        started = time.perf_counter()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file)
            frames = wav_file.getnframes()
        return Speech(
            wav=buffer.getvalue(),
            sample_rate=self.sample_rate,
            audio_seconds=frames / self.sample_rate,
            seconds=time.perf_counter() - started,
        )
