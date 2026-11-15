"""Configuration. Everything comes from environment variables, so the same code runs on the laptop,
in a container and on AKS; the defaults are the laptop values."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    models_dir: Path
    language: str  # spoken language, fixed (D5)

    stt_model: str  # directory name under models_dir
    stt_compute_type: str
    stt_threads: int
    stt_beam_size: int

    tts_voice: str  # directory name under models_dir

    openai_base_url: str  # any OpenAI-compatible endpoint: Ollama locally, Azure OpenAI later
    openai_api_key: str
    chat_model: str
    chat_max_tokens: int
    chat_reasoning_effort: str  # empty for classic chat models; set for reasoning models (Azure, later)

    # Services (D10-D13)
    stt_url: str  # base URL of the speech-to-text service, as the gateway reaches it
    tts_url: str  # base URL of the text-to-speech service
    max_upload_bytes: int  # one recorded question
    max_audio_seconds: float  # one question, after decoding
    max_speech_chars: int  # one answer to speak
    max_waiting: int  # requests a speech service queues behind the one it is working on; more get 503

    @property
    def stt_model_dir(self) -> Path:
        return self.models_dir / self.stt_model

    @property
    def tts_voice_dir(self) -> Path:
        return self.models_dir / self.tts_voice


def default_threads() -> int:
    """CPUs this process may use (respects container CPU pinning), capped: Whisper gains little beyond 8."""
    return max(1, min(len(os.sched_getaffinity(0)), 8))


def load(env: dict[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    return Settings(
        models_dir=Path(env.get("MODELS_DIR", "models")),
        language=env.get("VOICE_LANGUAGE", "ar"),
        stt_model=env.get("STT_MODEL", "stt-small"),
        stt_compute_type=env.get("STT_COMPUTE_TYPE", "int8"),
        stt_threads=int(env.get("STT_THREADS", "0")) or default_threads(),
        stt_beam_size=int(env.get("STT_BEAM_SIZE", "5")),
        tts_voice=env.get("TTS_VOICE", "tts-ar-kareem-medium"),
        openai_base_url=env.get("OPENAI_BASE_URL", "http://127.0.0.1:11434/v1"),
        openai_api_key=env.get("OPENAI_API_KEY", "ollama"),  # Ollama ignores the key; the SDK requires one
        chat_model=env.get("CHAT_MODEL", "phi4-mini:3.8b"),
        chat_max_tokens=int(env.get("CHAT_MAX_TOKENS", "160")),
        chat_reasoning_effort=env.get("CHAT_REASONING_EFFORT", ""),
        stt_url=env.get("STT_URL", "http://127.0.0.1:8001/v1"),
        tts_url=env.get("TTS_URL", "http://127.0.0.1:8002/v1"),
        max_upload_bytes=int(env.get("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024))),
        max_audio_seconds=float(env.get("MAX_AUDIO_SECONDS", "20")),
        max_speech_chars=int(env.get("MAX_SPEECH_CHARS", "600")),
        max_waiting=int(env.get("MAX_WAITING", "4")),
    )
