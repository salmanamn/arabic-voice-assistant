import os
from pathlib import Path

import pytest

from voice.settings import default_threads, load, physical_cores


def test_defaults_are_the_laptop_values():
    settings = load({})
    assert settings.models_dir == Path("models")
    assert settings.language == "ar"
    assert settings.stt_model_dir == Path("models/stt-small")
    assert settings.stt_compute_type == "int8"
    assert settings.stt_threads == default_threads()
    assert 1 <= settings.stt_threads <= 8
    assert settings.tts_voice_dir == Path("models/tts-ar-kareem-medium")
    assert settings.openai_base_url == "http://127.0.0.1:11434/v1"
    assert settings.openai_auth == "key"
    assert settings.chat_model == "phi4-mini:3.8b"
    assert settings.chat_reasoning_effort == ""
    assert settings.stt_url == "http://127.0.0.1:8001/v1"
    assert settings.tts_url == "http://127.0.0.1:8002/v1"
    assert settings.max_upload_bytes == 2 * 1024 * 1024
    assert settings.max_audio_seconds == 20.0
    assert settings.max_speech_chars == 600
    assert settings.max_waiting == 4


def test_environment_overrides():
    settings = load(
        {
            "MODELS_DIR": "/models",
            "STT_MODEL": "stt-turbo",
            "STT_THREADS": "3",
            "STT_BEAM_SIZE": "1",
            "OPENAI_BASE_URL": "https://example.openai.azure.com/openai/v1",
            "CHAT_MODEL": "gpt-5.4-mini",
            "CHAT_REASONING_EFFORT": "low",
            "CHAT_MAX_TOKENS": "400",
            "STT_URL": "http://stt:8000/v1",
            "MAX_WAITING": "0",
        }
    )
    assert settings.stt_model_dir == Path("/models/stt-turbo")
    assert settings.stt_threads == 3
    assert settings.stt_beam_size == 1
    assert settings.openai_base_url == "https://example.openai.azure.com/openai/v1"
    assert settings.chat_model == "gpt-5.4-mini"
    assert settings.chat_reasoning_effort == "low"
    assert settings.chat_max_tokens == 400
    assert settings.stt_url == "http://stt:8000/v1"
    assert settings.max_waiting == 0


def test_unknown_openai_auth_is_refused():
    with pytest.raises(ValueError, match="OPENAI_AUTH"):
        load({"OPENAI_AUTH": "managed-identity"})


def fake_sysfs(root, siblings: dict[int, str], name: str = "core_cpus_list"):
    for cpu, value in siblings.items():
        topology = root / f"cpu{cpu}" / "topology"
        topology.mkdir(parents=True)
        (topology / name).write_text(value + "\n")
    return root


# An i7-9750H as Linux numbers it: 6 cores, 12 CPUs, CPU n and n+6 share a core.
I7_9750H = {cpu: f"{cpu % 6},{cpu % 6 + 6}" for cpu in range(12)}


@pytest.mark.parametrize(
    ("cpus", "cores"),
    [
        (range(12), 6),  # every CPU: hyper-threads count once
        ([0, 6], 1),  # both threads of one core
        ([0, 1, 2], 3),  # one thread of three cores
        ([0, 1, 2, 6, 7, 8], 3),
        ([], 0),
    ],
)
def test_physical_cores_counts_hyper_threads_once(tmp_path, cpus, cores):
    assert physical_cores(cpus, fake_sysfs(tmp_path, I7_9750H)) == cores


def test_physical_cores_reads_range_lists_and_the_older_file_name(tmp_path):
    sysfs = fake_sysfs(tmp_path, {0: "0-1", 1: "0-1", 2: "2-3", 3: "2-3"}, name="thread_siblings_list")
    assert physical_cores(range(4), sysfs) == 2


def test_without_topology_every_cpu_is_a_core(tmp_path):
    assert physical_cores(range(5), tmp_path) == 5


def test_default_threads_follows_affinity_and_the_cap(tmp_path, monkeypatch):
    sysfs = fake_sysfs(tmp_path, {cpu: str(cpu) for cpu in range(16)})  # 16 cores without hyper-threading
    monkeypatch.setattr(os, "sched_getaffinity", lambda _: set(range(16)))
    assert default_threads(sysfs) == 8
    monkeypatch.setattr(os, "sched_getaffinity", lambda _: {0, 1, 2})
    assert default_threads(sysfs) == 3
    monkeypatch.setattr(os, "sched_getaffinity", lambda _: set(range(12)))
    assert default_threads(fake_sysfs(tmp_path / "i7", I7_9750H)) == 6


def test_speech_backends_default_to_our_pods():
    settings = load({})
    assert (settings.stt_backend, settings.tts_backend) == ("local", "local")
    assert (settings.azure_speech_locale, settings.azure_speech_voice) == ("ar-BH", "ar-BH-AliNeural")
    assert settings.azure_speech_stt_url == ""  # no region, no URL: nothing points at Azure


def test_unknown_speech_backend_is_refused():
    with pytest.raises(ValueError, match="TTS_BACKEND"):
        load({"TTS_BACKEND": "google"})


@pytest.mark.parametrize(
    ("env", "missing"),
    [
        ({"STT_BACKEND": "azure"}, "AZURE_SPEECH_RESOURCE_ID, AZURE_SPEECH_REGION"),
        ({"TTS_BACKEND": "azure", "AZURE_SPEECH_REGION": "uaenorth"}, "AZURE_SPEECH_RESOURCE_ID"),
        ({"STT_BACKEND": "azure", "AZURE_SPEECH_RESOURCE_ID": "/x", "AZURE_SPEECH_STT_URL": "https://a"}, "REGION"),
    ],
)
def test_azure_backend_needs_its_account(env, missing):
    with pytest.raises(ValueError, match=missing):
        load(env)


def test_explicit_urls_replace_the_regional_ones():
    custom = "https://spch-x.cognitiveservices.azure.com"
    settings = load(
        {
            "STT_BACKEND": "azure",
            "AZURE_SPEECH_RESOURCE_ID": "/x",
            "AZURE_SPEECH_STT_URL": f"{custom}/stt/speech/recognition/conversation/cognitiveservices/v1",
            "AZURE_SPEECH_TTS_URL": f"{custom}/tts/cognitiveservices/v1",
        }
    )
    assert settings.azure_speech_stt_url.startswith(custom)
    assert settings.azure_speech_tts_url == f"{custom}/tts/cognitiveservices/v1"
