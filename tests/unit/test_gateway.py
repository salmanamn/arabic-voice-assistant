"""The gateway against real HTTP servers: the two speech services with fake engines and a fake chat endpoint."""

import base64
import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from voice.azure_speech import SpeechFailure
from voice.services.gateway_app import create_app, speakable
from voice.services.stt_app import create_app as create_stt
from voice.services.tts_app import create_app as create_tts
from voice.settings import load
from voice.stt import SAMPLE_RATE, Transcript
from voice.tts import Speech

QUESTION = "ما هي عاصمة مملكة البحرين؟"
ANSWER = "**عاصمة مملكة البحرين** هي المنامة. 😀"
WAV = b"RIFF\x24\x00\x00\x00WAVEfake-answer"


class Recogniser:
    heard = QUESTION

    def decode(self, audio):
        import numpy as np

        data = audio.read()
        if data.startswith(b"bad"):
            raise ValueError("not audio")
        return np.zeros(2 * SAMPLE_RATE, dtype=np.float32)

    def transcribe(self, samples):
        return Transcript(text=self.heard, audio_seconds=2.0, seconds=0.01)


class Synthesiser:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def synthesize(self, text):
        self.spoken.append(text)
        return Speech(wav=WAV, sample_rate=22050, audio_seconds=1.0, seconds=0.01)


def chat_app(calls: list[dict], answer: str = ANSWER, status: int = 200) -> FastAPI:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def completions(request: Request):
        body = await request.json()
        calls.append(body)
        if status != 200:
            return JSONResponse({"error": {"code": "boom", "message": "x"}}, status_code=status)
        return {
            "id": "c",
            "object": "chat.completion",
            "created": 0,
            "model": body["model"],
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": answer}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    return app


@pytest.fixture
def lab(serve):
    """Starts the services; returns a function that builds a gateway client with optional overrides."""
    recogniser, synthesiser, calls = Recogniser(), Synthesiser(), []
    base = load({"MAX_UPLOAD_BYTES": "1000", "MAX_SPEECH_CHARS": "40"})
    clients: dict[str, list] = {"stt": [], "tts": []}
    stt_app, tts_app = create_stt(base, lambda _: recogniser), create_tts(base, lambda _: synthesiser)
    for name, app in (("stt", stt_app), ("tts", tts_app)):

        @app.middleware("http")
        async def record_client(request: Request, call_next, seen=clients[name]):
            seen.append(request.client.port)  # the gateway's end of the connection: a new port is a new connection
            return await call_next(request)

    urls = {
        "STT_URL": serve(stt_app) + "/v1",
        "TTS_URL": serve(tts_app) + "/v1",
        "OPENAI_BASE_URL": serve(chat_app(calls)) + "/v1",
    }

    def gateway(**overrides) -> TestClient:
        env = {"MAX_UPLOAD_BYTES": "1000", "MAX_SPEECH_CHARS": "40", **urls, **overrides}
        return TestClient(create_app(load(env)))

    gateway.recogniser, gateway.synthesiser, gateway.calls, gateway.urls = recogniser, synthesiser, calls, urls
    gateway.clients = clients
    return gateway


def turn(client: TestClient, data: bytes = b"recorded audio"):
    return client.post("/api/turn", files={"file": ("question.webm", data, "audio/webm")})


def test_a_full_turn(lab):
    response = turn(lab())

    assert response.status_code == 200
    body = response.json()
    assert body["heard"] == QUESTION
    assert body["answer"] == "عاصمة مملكة البحرين هي المنامة."  # cleaned for speech
    assert base64.b64decode(body["audio"]) == WAV
    assert set(body["timings"]) == {"stt", "chat", "tts", "total"}
    assert lab.synthesiser.spoken == ["عاصمة مملكة البحرين هي المنامة."]
    (call,) = lab.calls
    assert call["messages"][-1] == {"role": "user", "content": QUESTION}


def test_every_speech_call_is_a_new_connection(lab):
    # replicas behind a Service only share the work if connections are not kept alive (D27)
    client = lab()
    for _ in range(3):
        assert turn(client).status_code == 200
    for name in ("stt", "tts"):
        ports = lab.clients[name]
        assert len(ports) == 3
        assert len(set(ports)) == 3, f"{name}: a connection was reused"


def test_no_speech_means_no_chat_and_no_audio(lab):
    lab.recogniser.heard = ""
    body = turn(lab()).json()
    assert body == {"heard": "", "answer": "", "audio": None, "timings": body["timings"]}
    assert set(body["timings"]) == {"stt", "total"}
    assert lab.calls == []
    assert lab.synthesiser.spoken == []


def test_recording_that_is_not_audio_is_the_callers_error(lab):
    response = turn(lab(), b"bad bytes")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_audio"


def test_recording_over_the_limit_is_refused_before_any_call(lab):
    response = turn(lab(), b"x" * 1001)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "too_large"
    assert lab.calls == []


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"STT_URL": "http://127.0.0.1:9/v1"}, "stt_unavailable"),
        ({"OPENAI_BASE_URL": "http://127.0.0.1:9/v1"}, "chat_unavailable"),
        ({"TTS_URL": "http://127.0.0.1:9/v1"}, "tts_unavailable"),
    ],
)
def test_an_unreachable_dependency_is_named(lab, override, code):
    response = turn(lab(**override))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == code


def test_chat_server_error_is_a_bad_gateway(lab, serve):
    failing = serve(chat_app([], status=500)) + "/v1"
    response = turn(lab(OPENAI_BASE_URL=failing))
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "chat_failed"


def test_logs_carry_lengths_not_words(lab, caplog):
    with caplog.at_level(logging.INFO, logger="voice"):
        assert turn(lab()).status_code == 200
    text = caplog.text
    assert "heard 26 chars" in text
    assert "عاصمة" not in text
    assert "المنامة" not in text


def test_page_is_served_right_to_left(lab):
    response = lab().get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'dir="rtl"' in response.text
    assert "/api/turn" in response.text


def test_gateway_is_ready_without_its_dependencies(lab):
    client = lab(STT_URL="http://127.0.0.1:9/v1", TTS_URL="http://127.0.0.1:9/v1")
    assert client.get("/readyz").status_code == 200


@pytest.mark.parametrize(
    ("text", "limit", "expected"),
    [
        ("نعم.", 40, "نعم."),
        ("- أولا\n- ثانيا", 40, "أولا ثانيا"),
        ("كلمة أخرى ثالثة رابعة", 15, "كلمة أخرى"),
        ("😀", 40, ""),
    ],
)
def test_speakable(text, limit, expected):
    assert speakable(text, limit) == expected


class Cloud:
    """Stands in for voice.azure_speech.AzureSpeech: records what the gateway sends, or fails like it does."""

    def __init__(self, failure: SpeechFailure | None = None) -> None:
        self.heard: list[bytes] = []
        self.spoken: list[str] = []
        self.failure = failure

    def transcribe(self, data: bytes) -> Transcript:
        if self.failure:
            raise self.failure
        self.heard.append(data)
        return Transcript(text=QUESTION, audio_seconds=2.0, seconds=0.01)

    def speak(self, text: str) -> bytes:
        self.spoken.append(text)
        return b"RIFF\x24\x00\x00\x00WAVEazure"


AZURE = {"AZURE_SPEECH_RESOURCE_ID": "/subscriptions/s/x", "AZURE_SPEECH_REGION": "uaenorth"}


def test_azure_speech_replaces_both_speech_services(lab):
    cloud = Cloud()
    env = {**lab.urls, "STT_BACKEND": "azure", "TTS_BACKEND": "azure", **AZURE}
    response = turn(TestClient(create_app(load(env), cloud=cloud)), b"RIFF question")
    assert response.status_code == 200
    assert base64.b64decode(response.json()["audio"]) == b"RIFF\x24\x00\x00\x00WAVEazure"
    assert cloud.heard == [b"RIFF question"]
    assert cloud.spoken == ["عاصمة مملكة البحرين هي المنامة."]
    assert lab.clients == {"stt": [], "tts": []}  # our pods got nothing
    assert lab.synthesiser.spoken == []


def test_one_backend_can_stay_local(lab):
    cloud = Cloud()
    env = {**lab.urls, "STT_BACKEND": "azure", **AZURE}
    assert turn(TestClient(create_app(load(env), cloud=cloud))).status_code == 200
    assert len(cloud.heard) == 1 and cloud.spoken == []
    assert len(lab.clients["tts"]) == 1 and lab.clients["stt"] == []


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [
        (SpeechFailure(503, "busy"), 503, "stt_busy"),
        (SpeechFailure(503, "unavailable"), 503, "stt_unavailable"),
        (SpeechFailure(502, "failed"), 502, "stt_failed"),
        (SpeechFailure(400, "unsupported_audio"), 400, "unsupported_audio"),
        (SpeechFailure(413, "too_long"), 413, "too_long"),
    ],
)
def test_azure_speech_failures_keep_the_gateways_codes(lab, failure, status, code):
    env = {**lab.urls, "STT_BACKEND": "azure", **AZURE}
    response = turn(TestClient(create_app(load(env), cloud=Cloud(failure))))
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert lab.calls == []  # no answer asked for when the question wasn't heard
