"""Configuration. Everything comes from environment variables, so the same code runs on the laptop,
in a container and on AKS; the defaults are the laptop values."""

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

SYSFS_CPU = Path("/sys/devices/system/cpu")
MAX_THREADS = 8  # Whisper gains little beyond 8 threads


@dataclass(frozen=True)
class Settings:
    models_dir: Path
    language: str  # spoken language, fixed (D5)

    stt_model: str  # directory name under models_dir
    stt_compute_type: str
    stt_threads: int
    stt_beam_size: int

    tts_voice: str  # directory name under models_dir

    openai_base_url: str  # any OpenAI-compatible endpoint: Ollama locally, Azure OpenAI on AKS
    openai_auth: str  # "key": openai_api_key (Ollama); "entra": an Entra ID token (Azure OpenAI, D45)
    openai_api_key: str
    chat_model: str
    chat_max_tokens: int
    chat_reasoning_effort: str  # empty for classic chat models; set for reasoning models (Azure)

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


def physical_cores(cpus: Iterable[int], sysfs: Path = SYSFS_CPU) -> int:
    """Physical cores among `cpus`. Hyper-threads of one core share its arithmetic units, so they count once.

    Each CPU's `topology/core_cpus_list` names every CPU on the same core (for example "0,6" or "0-1"); CPUs with
    the same list are one core. Older kernels only have `thread_siblings_list`; without either file each CPU counts
    as a core of its own.
    """
    cores = set()
    for cpu in cpus:
        topology = sysfs / f"cpu{cpu}" / "topology"
        for name in ("core_cpus_list", "thread_siblings_list"):
            try:
                cores.add((topology / name).read_text().strip())
                break
            except OSError:
                continue
        else:
            cores.add(f"cpu{cpu}")
    return len(cores)


def default_threads(sysfs: Path = SYSFS_CPU) -> int:
    """Physical cores this process may run on (respects CPU pinning), capped at MAX_THREADS (D7)."""
    return max(1, min(physical_cores(os.sched_getaffinity(0), sysfs), MAX_THREADS))


OPENAI_AUTH = ("key", "entra")


def load(env: dict[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    auth = env.get("OPENAI_AUTH", "key")
    if auth not in OPENAI_AUTH:
        raise ValueError(f"OPENAI_AUTH must be one of {', '.join(OPENAI_AUTH)}, not {auth!r}")
    return Settings(
        models_dir=Path(env.get("MODELS_DIR", "models")),
        language=env.get("VOICE_LANGUAGE", "ar"),
        stt_model=env.get("STT_MODEL", "stt-small"),
        stt_compute_type=env.get("STT_COMPUTE_TYPE", "int8"),
        stt_threads=int(env.get("STT_THREADS", "0")) or default_threads(),
        stt_beam_size=int(env.get("STT_BEAM_SIZE", "5")),
        tts_voice=env.get("TTS_VOICE", "tts-ar-kareem-medium"),
        openai_base_url=env.get("OPENAI_BASE_URL", "http://127.0.0.1:11434/v1"),
        openai_auth=auth,
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
