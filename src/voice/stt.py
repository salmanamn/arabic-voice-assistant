"""Speech to text: faster-whisper (Whisper on CTranslate2), CPU."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from voice.settings import Settings

REQUIRED_FILES = ("model.bin", "config.json", "tokenizer.json")


@dataclass(frozen=True)
class Transcript:
    text: str
    audio_seconds: float
    seconds: float  # wall time: decoding the audio file + recognition

    @property
    def rtf(self) -> float:
        """Real-time factor: processing time / audio time (below 1 is faster than speech)."""
        return self.seconds / self.audio_seconds if self.audio_seconds else 0.0


class SpeechToText:
    def __init__(
        self, model_dir: Path, *, language: str = "ar", compute_type: str = "int8", threads: int = 4, beam_size: int = 5
    ) -> None:
        from faster_whisper import WhisperModel  # imported here: only the speech-to-text side needs CTranslate2

        # Without these checks faster-whisper would try to download what is missing from the Hugging Face Hub.
        missing = [name for name in REQUIRED_FILES if not (model_dir / name).is_file()]
        if missing:
            raise FileNotFoundError(f"{model_dir}: missing {', '.join(missing)} (run scripts/fetch_models.py)")
        self.language = language
        self.beam_size = beam_size
        self._model = WhisperModel(str(model_dir), device="cpu", compute_type=compute_type, cpu_threads=threads)

    @classmethod
    def from_settings(cls, settings: Settings) -> "SpeechToText":
        return cls(
            settings.stt_model_dir,
            language=settings.language,
            compute_type=settings.stt_compute_type,
            threads=settings.stt_threads,
            beam_size=settings.stt_beam_size,
        )

    def transcribe(self, audio: str | Path | BinaryIO) -> Transcript:
        """Transcribe one utterance. `audio` is a file path or a binary file object (any format FFmpeg reads)."""
        started = time.perf_counter()
        segments, info = self._model.transcribe(
            str(audio) if isinstance(audio, Path) else audio,
            language=self.language,  # fixed: no language detection on short utterances (D5)
            task="transcribe",
            beam_size=self.beam_size,
            condition_on_previous_text=False,  # utterances are independent; avoids repetition loops
            vad_filter=True,  # drop silence before recognition: Whisper invents text for non-speech
            without_timestamps=True,
        )
        text = " ".join(segment.text.strip() for segment in segments)  # the generator does the work here
        return Transcript(text=text.strip(), audio_seconds=info.duration, seconds=time.perf_counter() - started)
