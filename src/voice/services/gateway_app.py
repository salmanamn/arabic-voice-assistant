"""Gateway: one assistant turn over HTTP, and the push-to-talk page.

GET  /            the page (record a question in the browser, hear the answer)
POST /api/turn    multipart: file (the recorded question) ->
                  JSON {heard, answer, audio (base64 WAV or null), timings {stt, chat, tts, total}}
GET  /healthz, /readyz

The gateway holds no model. Speech goes to the speech services through their OpenAI-style routes and the
answer to the chat endpoint, all with the `openai` SDK, so any of the three can be swapped for a hosted
service by changing a URL (D10).

Run: uv run uvicorn --factory voice.services.gateway_app:create_app --port 8080
"""

import base64
import logging
import time
from pathlib import Path
from typing import Annotated

import httpx2
import openai
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from openai import OpenAI
from starlette.concurrency import run_in_threadpool

from voice.llm import Assistant
from voice.services.common import error, install_common
from voice.settings import Settings, load
from voice.textnorm import clean_for_speech

log = logging.getLogger("voice.gateway")
PAGE = Path(__file__).parent / "static" / "index.html"
SPEECH_KEY = "unused"  # the local speech services take no key; the SDK requires one


def speakable(text: str, limit: int) -> str:
    """The answer as it will be spoken: cleaned, and cut at a word boundary if it is over the speech limit."""
    text = clean_for_speech(text)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0]


def upstream_error(stage: str, exc: Exception):
    """Map a failed call to a speech service or the chat endpoint to one gateway error."""
    if isinstance(exc, openai.APIConnectionError):  # includes timeouts
        return error(503, f"{stage}_unavailable", f"the {stage} service did not answer")
    if isinstance(exc, openai.APIStatusError):
        code = exc.body.get("code") if isinstance(exc.body, dict) else None  # the SDK unwraps {"error": {...}}
        if exc.status_code in (400, 413) and stage == "stt":
            # the question itself was refused (not audio, too long): the caller can fix that
            return error(exc.status_code, code or "invalid_audio", "the speech service refused the recording")
        if exc.status_code == 503:
            return error(503, f"{stage}_busy", f"the {stage} service is busy; retry later")
    return error(502, f"{stage}_failed", f"the {stage} step failed")


def speech_client(base_url: str, timeout: float) -> OpenAI:
    """A client for one speech service that opens a new connection for every call (D27).

    A kept-alive connection stays with the replica it was opened to: on Kubernetes the Service spreads connections,
    not requests, so replicas added by the autoscaler would get no work from a busy gateway. A call takes seconds;
    one more connection inside the cluster costs about a millisecond.
    """
    limits = httpx2.Limits(max_connections=None, max_keepalive_connections=0)
    return OpenAI(
        base_url=base_url,
        api_key=SPEECH_KEY,
        timeout=timeout,
        max_retries=0,
        http_client=openai.DefaultHttpxClient(limits=limits),
    )


def create_app(settings: Settings | None = None, assistant: Assistant | None = None):
    settings = settings or load()
    stt = speech_client(settings.stt_url, timeout=120.0)
    tts = speech_client(settings.tts_url, timeout=60.0)
    chat = assistant or Assistant.from_settings(settings)

    app = FastAPI(title="voice-gateway", docs_url=None, redoc_url=None)
    install_common(app, is_ready=lambda: True)

    @app.get("/", include_in_schema=False)
    async def page() -> FileResponse:
        return FileResponse(PAGE, media_type="text/html")

    @app.post("/api/turn")
    async def turn(file: Annotated[UploadFile, File()]) -> dict:
        data = await file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise error(413, "too_large", f"recording larger than {settings.max_upload_bytes} bytes")
        if not data:
            raise error(400, "empty_file", "the recording is empty")
        started = time.perf_counter()
        timings: dict[str, float] = {}

        upload = (file.filename or "question", data, file.content_type or "application/octet-stream")
        try:
            transcription = await run_in_threadpool(
                stt.audio.transcriptions.create, model=settings.stt_model, file=upload, language=settings.language
            )
        except openai.OpenAIError as exc:
            raise upstream_error("stt", exc) from None
        heard = transcription.text.strip()
        timings["stt"] = time.perf_counter() - started

        if not heard:
            log.info("turn: no speech in %d bytes (stt %.2f s)", len(data), timings["stt"])
            return {"heard": "", "answer": "", "audio": None, "timings": _rounded(timings, started)}

        mark = time.perf_counter()
        try:
            reply = await run_in_threadpool(chat.reply, heard)
        except openai.OpenAIError as exc:
            raise upstream_error("chat", exc) from None
        answer = speakable(reply.text, settings.max_speech_chars)
        timings["chat"] = time.perf_counter() - mark

        audio = None
        if answer:
            mark = time.perf_counter()
            try:
                speech = await run_in_threadpool(
                    tts.audio.speech.create, model="piper", voice="default", input=answer, response_format="wav"
                )
            except openai.OpenAIError as exc:
                raise upstream_error("tts", exc) from None
            audio = base64.b64encode(speech.content).decode("ascii")
            timings["tts"] = time.perf_counter() - mark

        result = _rounded(timings, started)
        # Lengths and times only: what the user said and heard stays out of the logs.
        log.info("turn: heard %d chars, answered %d chars, %s", len(heard), len(answer), result)
        return {"heard": heard, "answer": answer, "audio": audio, "timings": result}

    return app


def _rounded(timings: dict[str, float], started: float) -> dict[str, float]:
    return {**{k: round(v, 2) for k, v in timings.items()}, "total": round(time.perf_counter() - started, 2)}
