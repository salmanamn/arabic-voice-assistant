"""Azure AI Speech adapter (D59): keyless requests in the shape the Speech REST APIs take, audio checked before a call,
failures in the gateway's vocabulary. A mock transport stands in for Azure; nothing leaves the machine."""

import io
import json
import wave

import httpx2
import pytest

from voice.azure_speech import TTS_FORMAT, AzureSpeech, SpeechFailure, audio_content_type, check, ssml
from voice.settings import load

RESOURCE = "/subscriptions/s/resourceGroups/rg-voice-azure/providers/Microsoft.CognitiveServices/accounts/spch-x"
STT_URL = "https://uaenorth.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
TTS_URL = "https://uaenorth.tts.speech.microsoft.com/cognitiveservices/v1"
ANSWER_WAV = b"RIFF\x24\x00\x00\x00WAVEazure-answer"


def wav(seconds: float = 2.0, rate: int = 16000, channels: int = 1, width: int = 2) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes(b"\x00" * int(seconds * rate) * channels * width)
    return buffer.getvalue()


class Azure:
    """Records every request and answers like the service."""

    def __init__(self, stt_body: dict | None = None, status: int = 200, tts_body: bytes = ANSWER_WAV) -> None:
        self.requests: list[httpx2.Request] = []
        self.stt_body = stt_body or {"RecognitionStatus": "Success", "DisplayText": "ما هي عاصمة البحرين؟"}
        self.status = status
        self.tts_body = tts_body

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx2.Response(self.status, json={"error": "x"})
        if request.url.host.endswith("stt.speech.microsoft.com"):
            return httpx2.Response(200, json=self.stt_body)
        return httpx2.Response(200, content=self.tts_body)


def client(azure: Azure, max_audio_seconds: float = 20.0) -> AzureSpeech:
    return AzureSpeech(
        stt_url=STT_URL,
        tts_url=TTS_URL,
        resource_id=RESOURCE,
        locale="ar-BH",
        voice="ar-BH-AliNeural",
        token=lambda: "entra-token",
        max_audio_seconds=max_audio_seconds,
        transport=httpx2.MockTransport(azure),
    )


def test_recognition_is_keyless_with_the_resource_in_the_token():
    azure = Azure()
    heard = client(azure).transcribe(wav())
    assert heard.text == "ما هي عاصمة البحرين؟"
    (request,) = azure.requests
    assert request.headers["Authorization"] == f"Bearer aad#{RESOURCE}#entra-token"
    assert "Ocp-Apim-Subscription-Key" not in request.headers
    assert request.headers["Content-Type"] == "audio/wav; codecs=audio/pcm; samplerate=16000"
    assert request.url.params["language"] == "ar-BH"
    assert request.url.params["format"] == "simple"


def test_no_speech_is_an_empty_transcript():
    for status in ("NoMatch", "InitialSilenceTimeout"):
        assert client(Azure({"RecognitionStatus": status})).transcribe(wav()).text == ""


def test_ogg_opus_goes_as_is():
    assert audio_content_type(b"OggS" + b"\x00" * 40, 20) == "audio/ogg; codecs=opus"


@pytest.mark.parametrize(
    ("data", "status", "reason"),
    [
        (wav(rate=44100), 400, "unsupported_audio"),  # the short-audio API takes 16 kHz only
        (wav(channels=2), 400, "unsupported_audio"),
        (b"\x1aE\xdf\xa3webm", 400, "unsupported_audio"),  # WebM from Chrome's recorder
        (wav(seconds=21), 413, "too_long"),  # the gateway's own limit (MAX_AUDIO_SECONDS)
    ],
)
def test_audio_the_api_cant_take_is_refused_before_a_call(data, status, reason):
    azure = Azure()
    with pytest.raises(SpeechFailure) as failed:
        client(azure).transcribe(data)
    assert (failed.value.status, failed.value.reason) == (status, reason)
    assert azure.requests == []


@pytest.mark.parametrize(
    ("status", "expected"),
    [(429, (503, "busy")), (503, (503, "unavailable")), (401, (502, "failed")), (403, (502, "failed"))],
)
def test_service_errors_map_to_the_gateways_codes(status, expected):
    with pytest.raises(SpeechFailure) as failed:
        client(Azure(status=status)).transcribe(wav())
    assert (failed.value.status, failed.value.reason) == expected


def test_recognition_error_status_is_a_failure():
    with pytest.raises(SpeechFailure) as failed:
        client(Azure({"RecognitionStatus": "Error"})).transcribe(wav())
    assert failed.value.reason == "failed"


def test_connection_error_is_unavailable():
    def refuse(request):
        raise httpx2.ConnectError("refused", request=request)

    speech = client(Azure())
    speech._http = httpx2.Client(transport=httpx2.MockTransport(refuse))
    with pytest.raises(SpeechFailure) as failed:
        speech.speak("مرحبا")
    assert failed.value.reason == "unavailable"


def test_synthesis_sends_escaped_ssml_and_asks_for_wav():
    azure = Azure()
    assert client(azure).speak("المنامة <عاصمة> & أكبر مدنها") == ANSWER_WAV
    (request,) = azure.requests
    assert request.headers["Authorization"] == f"Bearer aad#{RESOURCE}#entra-token"
    assert request.headers["X-Microsoft-OutputFormat"] == TTS_FORMAT == "riff-22050hz-16bit-mono-pcm"
    body = request.content.decode("utf-8")
    assert body == (
        '<speak version=\'1.0\' xml:lang="ar-BH"><voice name="ar-BH-AliNeural">'
        "المنامة &lt;عاصمة&gt; &amp; أكبر مدنها</voice></speak>"
    )


def test_synthesis_that_is_not_wav_is_a_failure():
    with pytest.raises(SpeechFailure):
        client(Azure(tts_body=json.dumps({"x": 1}).encode())).speak("مرحبا")


def test_ssml_quotes_attributes():
    assert ssml("x", "ar-BH", "a'b") == '<speak version=\'1.0\' xml:lang="ar-BH"><voice name="a\'b">x</voice></speak>'


def test_settings_build_the_regional_urls():
    settings = load({"STT_BACKEND": "azure", "AZURE_SPEECH_RESOURCE_ID": RESOURCE, "AZURE_SPEECH_REGION": "uaenorth"})
    speech = AzureSpeech.from_settings(settings, token=lambda: "t")
    assert (speech.stt_url, speech.tts_url, speech.locale, speech.voice) == (
        STT_URL,
        TTS_URL,
        "ar-BH",
        "ar-BH-AliNeural",
    )


def test_check_speaks_then_hears_it(capsys):
    azure = Azure(tts_body=wav(seconds=1.0))
    assert check(client(azure)) == 0
    synthesis, recognition = azure.requests
    assert synthesis.headers["X-Microsoft-OutputFormat"] == "riff-16khz-16bit-mono-pcm"
    assert recognition.content == wav(seconds=1.0)
    out = capsys.readouterr().out
    assert "OK   synthesis" in out and "OK   recognition (ar-BH)" in out and "entra-token" not in out


def test_check_names_azures_status(capsys):
    assert check(client(Azure(status=403))) == 1
    assert "FAIL failed (Azure answered HTTP 403)" in capsys.readouterr().out


def test_check_without_settings(capsys, monkeypatch):
    for name in ("AZURE_SPEECH_RESOURCE_ID", "AZURE_SPEECH_REGION", "AZURE_SPEECH_STT_URL", "AZURE_SPEECH_TTS_URL"):
        monkeypatch.delenv(name, raising=False)
    assert check() == 1
    assert "not configured" in capsys.readouterr().out
