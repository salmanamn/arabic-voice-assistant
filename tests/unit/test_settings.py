from pathlib import Path

from voice.settings import default_threads, load


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
    assert settings.chat_model == "phi4-mini:3.8b"
    assert settings.chat_reasoning_effort == ""


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
        }
    )
    assert settings.stt_model_dir == Path("/models/stt-turbo")
    assert settings.stt_threads == 3
    assert settings.stt_beam_size == 1
    assert settings.openai_base_url == "https://example.openai.azure.com/openai/v1"
    assert settings.chat_model == "gpt-5.4-mini"
    assert settings.chat_reasoning_effort == "low"
    assert settings.chat_max_tokens == 400
