# arabic-voice-assistant

A voice assistant that listens and answers in Arabic, built from open components: **faster-whisper** turns speech into text, an LLM writes a short answer, **Piper** speaks it. It runs first on a laptop, then as services on Kubernetes (minikube with Helm), then on AKS.

**Status: M3 — measured on real Arabic speech; speech and chat models chosen by rule.** Three HTTP services and a push-to-talk page on the laptop; no containers or Kubernetes yet.

```
browser (push to talk) ──POST /api/turn──▶ gateway :8080 ──▶ stt :8001   POST /v1/audio/transcriptions  (faster-whisper)
                                                     ├──▶ chat        POST /v1/chat/completions      (Ollama)
                                                     └──▶ tts :8002   POST /v1/audio/speech          (Piper)
```

| Step | Component | Local | Planned on Azure |
|---|---|---|---|
| Speech to text | faster-whisper 1.2.1 (Whisper on CTranslate2), CPU, int8 | Whisper, chosen in M3 (D16) | same container on AKS |
| Answer | any OpenAI-compatible endpoint | Ollama, chosen in M3 (D17) | Azure OpenAI through workload identity |
| Text to speech | Piper 1.8.0, Arabic voice `ar_JO-kareem-medium` | same | same container on AKS |

The speech services speak OpenAI's audio routes, so the gateway uses one `openai` client for all three steps and any of them can be replaced by a hosted service by changing a URL.

## Run it

Needs uv, Docker and about 3.5 GB of downloads (models and packages) on first use.

    uv sync
    uv run python scripts/fetch_models.py stt-small tts-ar-kareem-medium
    docker compose up -d && docker exec voice-ollama ollama pull phi4-mini:3.8b

Then one terminal each:

    uv run uvicorn --factory voice.services.stt_app:create_app --port 8001
    uv run uvicorn --factory voice.services.tts_app:create_app --port 8002
    uv run uvicorn --factory voice.services.gateway_app:create_app --port 8080

Open http://localhost:8080, hold the button (or the space bar), ask a question in Arabic, let go.

Without a browser: `curl -s -F file=@question.wav http://127.0.0.1:8080/api/turn | jq 'del(.audio)'`.

Model files are not in this repository. `models.lock.json` pins each one to a repository revision and the SHA-256 of every file; `scripts/fetch_models.py --verify` checks what is on disk.

## What is measured so far

- `scripts/roundtrip.py`: eight sentences spoken by Piper and transcribed by faster-whisper. A smoke test of the pipeline and its speed, not of recognition (synthetic speech, one voice).
- **Real speech (M3):** 20 recorded questions (14 Modern Standard Arabic, 6 Gulf dialect) and 40 sentences of FLEURS Arabic (CC BY 4.0), Whisper small against large-v3-turbo; small chat models on 24 Arabic questions with known answers; and a time budget per stage, measured through the services. The comparison and the choices: [docs/evidence/m3-summary.md](docs/evidence/m3-summary.md). Audio is not in the repository; `scripts/speech_set.py` rebuilds the sets.

Design choices and their reasons: [docs/decisions.md](docs/decisions.md).