"""Text-to-speech service: OpenAI's speech route, served by Piper. The only process that imports Piper (D3).

POST /v1/audio/speech   JSON: input (required), model, voice, response_format (wav), speed (1.0)
GET  /healthz, /readyz

Run: uv run uvicorn --factory voice.services.tts_app:create_app --port 8002
"""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict

from voice.services.common import Worker, error, install_common
from voice.settings import Settings, load
from voice.textnorm import clean_for_speech
from voice.tts import Speech, TextToSpeech

log = logging.getLogger("voice.tts")


class Synthesiser(Protocol):
    def synthesize(self, text: str) -> Speech: ...


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")  # OpenAI clients may send fields this service has no use for

    input: str
    model: str = "piper"
    voice: str = "default"  # one voice per service (TTS_VOICE); the name is accepted, not used
    response_format: str = "wav"
    speed: float = 1.0


def create_app(settings: Settings | None = None, synthesiser_factory: Callable[[Settings], Synthesiser] | None = None):
    settings = settings or load()
    factory = synthesiser_factory or TextToSpeech.from_settings
    state: dict[str, Synthesiser] = {}
    worker = Worker(settings.max_waiting)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        state["synthesiser"] = factory(settings)
        log.info("text to speech ready: %s", settings.tts_voice)
        yield
        state.clear()

    app = FastAPI(title="voice-tts", lifespan=lifespan, docs_url=None, redoc_url=None)
    install_common(app, is_ready=lambda: "synthesiser" in state)

    @app.post("/v1/audio/speech")
    async def speech(request: SpeechRequest) -> Response:
        if request.response_format != "wav":
            raise error(400, "unsupported_format", "response_format must be wav")
        if request.speed != 1.0:
            raise error(400, "unsupported_speed", "speed must be 1.0")
        if len(request.input) > settings.max_speech_chars:
            raise error(413, "too_long", f"input longer than {settings.max_speech_chars} characters")
        if not clean_for_speech(request.input):
            raise error(400, "nothing_to_say", "input has no speakable text")

        result = await worker.run(state["synthesiser"].synthesize, request.input)
        log.info(
            "spoke %d chars as %.1f s of audio in %.2f s", len(request.input), result.audio_seconds, result.seconds
        )
        return Response(content=result.wav, media_type="audio/wav")

    return app
