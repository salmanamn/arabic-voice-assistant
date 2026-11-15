"""Speech-to-text service: OpenAI's transcription route, served by faster-whisper.

POST /v1/audio/transcriptions   multipart: file (required), model, language, response_format (json | text)
GET  /healthz, /readyz

Run: uv run uvicorn --factory voice.services.stt_app:create_app --port 8001
"""

import io
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Protocol

import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import PlainTextResponse

from voice.services.common import Worker, error, install_common
from voice.settings import Settings, load
from voice.stt import SAMPLE_RATE, SpeechToText, Transcript

log = logging.getLogger("voice.stt")


class Recogniser(Protocol):
    def decode(self, audio) -> np.ndarray: ...

    def transcribe(self, audio: np.ndarray) -> Transcript: ...


def create_app(settings: Settings | None = None, recogniser_factory: Callable[[Settings], Recogniser] | None = None):
    settings = settings or load()
    factory = recogniser_factory or SpeechToText.from_settings
    state: dict[str, Recogniser] = {}
    worker = Worker(settings.max_waiting)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        state["recogniser"] = factory(settings)  # loads the model before the port accepts requests
        log.info("speech to text ready: %s, %d threads", settings.stt_model, settings.stt_threads)
        yield
        state.clear()

    app = FastAPI(title="voice-stt", lifespan=lifespan, docs_url=None, redoc_url=None)
    install_common(app, is_ready=lambda: "recogniser" in state)

    @app.post("/v1/audio/transcriptions")
    async def transcriptions(
        file: Annotated[UploadFile, File()],
        model: Annotated[str, Form()] = settings.stt_model,  # accepted for compatibility; one model per service
        language: Annotated[str | None, Form()] = None,
        response_format: Annotated[str, Form()] = "json",
    ):
        if response_format not in ("json", "text"):
            raise error(400, "unsupported_format", "response_format must be json or text")
        if language not in (None, "", settings.language):
            raise error(400, "unsupported_language", f"this service transcribes language {settings.language!r} only")
        data = await file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise error(413, "too_large", f"audio file larger than {settings.max_upload_bytes} bytes")
        if not data:
            raise error(400, "empty_file", "the audio file is empty")

        try:
            transcript, seconds = await worker.run(_recognise, state["recogniser"], data, settings.max_audio_seconds)
        except InvalidAudio:
            raise error(400, "invalid_audio", "the file could not be decoded as audio") from None
        except TooLong:
            raise error(413, "too_long", f"audio longer than {settings.max_audio_seconds:g} seconds") from None
        log.info("transcribed %.1f s of audio in %.2f s, %d chars", seconds, transcript.seconds, len(transcript.text))
        if response_format == "text":
            return PlainTextResponse(transcript.text)
        return {"text": transcript.text, "duration": round(seconds, 3)}

    return app


class InvalidAudio(Exception):
    pass


class TooLong(Exception):
    pass


def _recognise(recogniser: Recogniser, data: bytes, max_seconds: float) -> tuple[Transcript, float]:
    """Decode, check the length, transcribe: one job for the worker, so one request takes one queue slot."""
    try:
        samples = recogniser.decode(io.BytesIO(data))
    except Exception as exc:  # FFmpeg raises several error types for input that is not audio
        raise InvalidAudio from exc
    seconds = len(samples) / SAMPLE_RATE
    if seconds > max_seconds:
        raise TooLong
    return recogniser.transcribe(samples), seconds
