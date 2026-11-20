"""Azure AI Speech as a drop-in for the stt and tts pods (optional, M9, D59): the gateway calls it instead of its own
speech services when STT_BACKEND or TTS_BACKEND is `azure`.

Keyless: every request carries an Entra ID token from the gateway's workload identity (DefaultAzureCredential, the
same as for Azure OpenAI, D45), in the form the Speech REST APIs take it: `Authorization: Bearer
aad#<resource id>#<token>`. The account has local (key) auth off; there is no key to send.

- Speech to text: the REST API for short audio (`…/speech/recognition/conversation/cognitiveservices/v1`), the one
  real-time recognition route UAE North offers (fast transcription is not in that region). It takes 16 kHz mono
  16-bit PCM WAV or Ogg Opus, at most 60 s; anything else is refused here, before a call is made.
- Text to speech: `…/cognitiveservices/v1` with SSML, answered as 22.05 kHz mono 16-bit WAV, the format Piper
  produces, so the page plays both the same way.

Errors become `SpeechFailure` with the gateway's vocabulary (unavailable | busy | failed, or 400 for audio this API
can't take); messages are fixed text and never contain what was said (D13).
"""

import io
import json
import time
import wave
from collections.abc import Callable
from dataclasses import dataclass
from xml.sax.saxutils import escape, quoteattr

import httpx2

from voice.settings import Settings, load

ENTRA_SCOPE = "https://cognitiveservices.azure.com/.default"
TTS_FORMAT = "riff-22050hz-16bit-mono-pcm"
NO_SPEECH = {"NoMatch", "InitialSilenceTimeout", "BabbleTimeout"}
MAX_SECONDS = 60.0  # the short-audio API's limit


class SpeechFailure(Exception):
    """One failed Azure Speech call, as the gateway reports it: HTTP status and the second half of its error code.
    `upstream` is Azure's own HTTP status (for the self-check's diagnosis; never shown to a caller)."""

    def __init__(self, status: int, reason: str, upstream: int | None = None) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason  # unavailable | busy | failed | unsupported_audio | too_long
        self.upstream = upstream


def token_provider() -> Callable[[], str]:
    """Entra ID tokens for Cognitive Services from the pod's workload identity (or `az login` on a laptop).
    Imported here: only the gateway image has azure-identity (D9)."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    return get_bearer_token_provider(DefaultAzureCredential(), ENTRA_SCOPE)


def audio_content_type(data: bytes, max_seconds: float) -> str:
    """The Content-Type the short-audio API needs for this recording, or SpeechFailure(400) for audio it can't take."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        try:
            with wave.open(io.BytesIO(data)) as wav:
                shape = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
                seconds = wav.getnframes() / wav.getframerate()
        except (wave.Error, EOFError, ZeroDivisionError):
            raise SpeechFailure(400, "unsupported_audio") from None
        if shape != (1, 2, 16000):
            raise SpeechFailure(400, "unsupported_audio")  # 16 kHz mono 16-bit PCM only
        if seconds > min(max_seconds, MAX_SECONDS):
            raise SpeechFailure(413, "too_long")
        return "audio/wav; codecs=audio/pcm; samplerate=16000"
    if data[:4] == b"OggS":
        return "audio/ogg; codecs=opus"  # length is checked by the service (60 s)
    raise SpeechFailure(400, "unsupported_audio")  # WebM, MP4/M4A, MP3: the stt pod decodes those, this API doesn't


def ssml(text: str, locale: str, voice: str) -> str:
    return (
        f"<speak version='1.0' xml:lang={quoteattr(locale)}>"
        f"<voice name={quoteattr(voice)}>{escape(text)}</voice></speak>"
    )


def _failure(response: httpx2.Response) -> SpeechFailure:
    code = response.status_code
    if code == 429:
        return SpeechFailure(503, "busy", code)
    if code >= 500:
        return SpeechFailure(503, "unavailable", code)
    return SpeechFailure(502, "failed", code)  # 400 for a request we built, 401/403: identity or role (D59)


@dataclass(frozen=True)
class Transcript:
    text: str
    seconds: float


class AzureSpeech:
    def __init__(
        self,
        *,
        stt_url: str,
        tts_url: str,
        resource_id: str,
        locale: str,
        voice: str,
        token: Callable[[], str],
        max_audio_seconds: float = 20.0,
        timeout: float = 30.0,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self.stt_url = stt_url
        self.tts_url = tts_url
        self.resource_id = resource_id
        self.locale = locale
        self.voice = voice
        self.max_audio_seconds = max_audio_seconds
        self._token = token
        # A new connection per call, like the gateway's own speech clients (D27); one call per turn either way.
        limits = httpx2.Limits(max_connections=None, max_keepalive_connections=0)
        self._http = httpx2.Client(timeout=timeout, limits=limits, transport=transport)

    @classmethod
    def from_settings(cls, settings: Settings, token: Callable[[], str] | None = None) -> "AzureSpeech":
        return cls(
            stt_url=settings.azure_speech_stt_url,
            tts_url=settings.azure_speech_tts_url,
            resource_id=settings.azure_speech_resource_id,
            locale=settings.azure_speech_locale,
            voice=settings.azure_speech_voice,
            token=token or token_provider(),
            max_audio_seconds=settings.max_audio_seconds,
        )

    def _authorization(self) -> str:
        # The Speech REST APIs take an Entra token together with the resource it is for (D59).
        return f"Bearer aad#{self.resource_id}#{self._token()}"

    def _post(self, url: str, **kwargs) -> httpx2.Response:
        try:
            response = self._http.post(url, **kwargs)
        except httpx2.HTTPError:
            raise SpeechFailure(503, "unavailable") from None
        if response.status_code != 200:
            raise _failure(response)
        return response

    def transcribe(self, data: bytes) -> Transcript:
        content_type = audio_content_type(data, self.max_audio_seconds)
        started = time.perf_counter()
        response = self._post(
            self.stt_url,
            params={"language": self.locale, "format": "simple"},
            headers={
                "Authorization": self._authorization(),
                "Content-Type": content_type,
                "Accept": "application/json",
            },
            content=data,
        )
        try:
            body = response.json()
            status = body["RecognitionStatus"]
        except (json.JSONDecodeError, KeyError, TypeError):
            raise SpeechFailure(502, "failed") from None
        if status in NO_SPEECH:
            text = ""
        elif status == "Success":
            text = str(body.get("DisplayText", "")).strip()
        else:
            raise SpeechFailure(502, "failed")
        return Transcript(text=text, seconds=time.perf_counter() - started)

    def speak(self, text: str, output_format: str = TTS_FORMAT) -> bytes:
        response = self._post(
            self.tts_url,
            headers={
                "Authorization": self._authorization(),
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": output_format,
                "User-Agent": "arabic-voice-assistant",
            },
            content=ssml(text, self.locale, self.voice).encode("utf-8"),
        )
        if response.content[:4] != b"RIFF":
            raise SpeechFailure(502, "failed")
        return response.content


CHECK_TEXT = "مرحبا، هذا اختبار للصوت."  # "Hello, this is a voice test."


def check(speech: AzureSpeech | None = None) -> int:
    """`python -m voice.azure_speech` in the gateway pod (D59): one synthesis, then recognition of that audio, with
    the pod's settings and its workload identity. Prints what happened and Azure's HTTP status on failure; no token,
    no key, no request body."""
    if speech is None:
        settings = load()
        if not (settings.azure_speech_resource_id and settings.azure_speech_stt_url and settings.azure_speech_tts_url):
            print("FAIL Azure Speech is not configured here (azureSpeech.enabled in the chart?)")
            return 1
        speech = AzureSpeech.from_settings(settings)
    try:
        wav = speech.speak(CHECK_TEXT, output_format="riff-16khz-16bit-mono-pcm")  # 16 kHz: what recognition takes
        print(f"OK   synthesis: {len(wav)} bytes of WAV, voice {speech.voice}")
        heard = speech.transcribe(wav)
        print(f"OK   recognition ({speech.locale}) in {heard.seconds:.2f} s: {heard.text}")
    except SpeechFailure as exc:
        print(f"FAIL {exc.reason} (Azure answered HTTP {exc.upstream or 'nothing'})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
