"""The two speech services, with fake engines: the HTTP contract, limits, and errors that never echo input."""

import asyncio

import numpy as np
import pytest
from fastapi.testclient import TestClient

from voice.services.common import Worker
from voice.services.stt_app import create_app as create_stt
from voice.services.tts_app import create_app as create_tts
from voice.settings import load
from voice.stt import SAMPLE_RATE, Transcript
from voice.tts import Speech

SETTINGS = load({"MAX_UPLOAD_BYTES": "1000", "MAX_AUDIO_SECONDS": "20", "MAX_SPEECH_CHARS": "50"})
MARKER = "علامة-123"  # sent in requests; must never come back in an error body


class FakeRecogniser:
    """Audio is the text b"seconds=<n>;text=<words>"; b"bad..." is not audio."""

    def decode(self, audio) -> np.ndarray:
        data = audio.read()
        if data.startswith(b"bad"):
            raise ValueError("Invalid data found when processing input")
        seconds = float(data.split(b";")[0].split(b"=")[1])
        self.last = data
        return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)

    def transcribe(self, samples: np.ndarray) -> Transcript:
        text = self.last.split(b"text=")[1].decode()
        return Transcript(text=text, audio_seconds=len(samples) / SAMPLE_RATE, seconds=0.01)


class FakeSynthesiser:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def synthesize(self, text: str) -> Speech:
        self.spoken.append(text)
        return Speech(wav=b"RIFF....WAVEfake", sample_rate=22050, audio_seconds=1.0, seconds=0.01)


def audio(seconds: float, text: str) -> bytes:
    return f"seconds={seconds};text={text}".encode()


@pytest.fixture
def stt():
    with TestClient(create_stt(SETTINGS, lambda _: FakeRecogniser())) as client:
        yield client


class SlowRecogniser(FakeRecogniser):
    def transcribe(self, samples):
        import time

        time.sleep(0.3)
        return Transcript(text="نعم", audio_seconds=1.0, seconds=0.3)


@pytest.fixture
def stt_slow():
    settings = load({"MAX_WAITING": "1"})
    with TestClient(create_stt(settings, lambda _: SlowRecogniser())) as client:
        yield client


@pytest.fixture
def synthesiser():
    return FakeSynthesiser()


@pytest.fixture
def tts(synthesiser):
    with TestClient(create_tts(SETTINGS, lambda _: synthesiser)) as client:
        yield client


def transcribe(client, data: bytes, **form):
    return client.post("/v1/audio/transcriptions", files={"file": ("q.webm", data, "audio/webm")}, data=form)


# --- speech to text -----------------------------------------------------------------------------------


def test_transcription_json(stt):
    response = transcribe(stt, audio(3.5, "ما هي عاصمة البحرين؟"), model="stt-small", language="ar")
    assert response.status_code == 200
    assert response.json() == {"text": "ما هي عاصمة البحرين؟", "duration": 3.5}


def test_transcription_text_format(stt):
    response = transcribe(stt, audio(1, "نعم"), response_format="text")
    assert response.status_code == 200
    assert response.text == "نعم"


def test_any_model_name_is_accepted(stt):
    assert transcribe(stt, audio(1, "نعم"), model="whisper-1").status_code == 200


@pytest.mark.parametrize(
    ("data", "form", "status", "code"),
    [
        (audio(1, "x"), {"language": "en"}, 400, "unsupported_language"),
        (audio(1, "x"), {"response_format": "srt"}, 400, "unsupported_format"),
        (b"", {}, 400, "empty_file"),
        (b"bad " + MARKER.encode(), {}, 400, "invalid_audio"),
        (audio(20.5, "x"), {}, 413, "too_long"),
        (b"x" * 1001, {}, 413, "too_large"),
    ],
)
def test_transcription_is_refused(stt, data, form, status, code):
    response = transcribe(stt, data, **form)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert MARKER not in response.text


def test_missing_file_names_the_field_without_echoing_input(stt):
    response = stt.post("/v1/audio/transcriptions", data={"model": MARKER})
    assert response.status_code == 400
    assert response.json() == {"error": {"code": "invalid_request", "message": "invalid or missing: file"}}


def test_requests_beyond_the_queue_get_503(stt_slow):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(3) as pool:
        codes = sorted(pool.map(lambda _: transcribe(stt_slow, audio(1, "نعم")).status_code, range(3)))
    assert codes == [200, 200, 503]  # one working, one waiting (MAX_WAITING=1), one refused


def test_health_and_ready(stt):
    assert stt.get("/healthz").json() == {"status": "ok"}
    assert stt.get("/readyz").status_code == 200


def test_not_ready_before_the_model_is_loaded():
    client = TestClient(create_stt(SETTINGS, lambda _: FakeRecogniser()))  # no `with`: lifespan not run
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "loading"}


# --- text to speech -----------------------------------------------------------------------------------


def test_speech_returns_wav(tts, synthesiser):
    response = tts.post("/v1/audio/speech", json={"model": "piper", "voice": "x", "input": "مرحبا بكم"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF....WAVEfake"
    assert synthesiser.spoken == ["مرحبا بكم"]


def test_speech_ignores_unknown_openai_fields(tts):
    response = tts.post("/v1/audio/speech", json={"input": "نعم", "instructions": "calm", "stream_format": "audio"})
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"input": "نعم", "response_format": "mp3"}, 400, "unsupported_format"),
        ({"input": "نعم", "speed": 1.5}, 400, "unsupported_speed"),
        ({"input": "😀 ✅ " + "#"}, 400, "nothing_to_say"),
        ({"input": "ا" * 51}, 413, "too_long"),
        ({"voice": MARKER}, 400, "invalid_request"),
    ],
)
def test_speech_is_refused(tts, synthesiser, body, status, code):
    response = tts.post("/v1/audio/speech", json=body)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert MARKER not in response.text
    assert synthesiser.spoken == []


# --- one model call at a time ---------------------------------------------------------------------------


def test_worker_runs_calls_one_at_a_time_and_refuses_beyond_the_queue():
    import threading
    import time

    active, peak, lock = 0, 0, threading.Lock()

    def work(n):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return n

    async def main():
        worker = Worker(max_waiting=2)
        results = await asyncio.gather(*(worker.run(work, n) for n in range(4)), return_exceptions=True)
        return worker, results

    worker, results = asyncio.run(main())
    assert results[:3] == [0, 1, 2]  # one running + two waiting
    assert getattr(results[3], "status_code", None) == 503
    assert peak == 1
    assert worker.waiting == 0


def test_worker_forgets_a_cancelled_waiter():
    import time

    async def main():
        worker = Worker(max_waiting=1)
        running = asyncio.create_task(worker.run(time.sleep, 0.1))
        await asyncio.sleep(0.01)
        waiting = asyncio.create_task(worker.run(time.sleep, 0))
        await asyncio.sleep(0.01)
        assert worker.waiting == 1
        waiting.cancel()
        await asyncio.gather(waiting, return_exceptions=True)
        assert worker.waiting == 0
        await running
        return await worker.run(lambda: "free again")

    assert asyncio.run(main()) == "free again"
