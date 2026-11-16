# arabic-voice-assistant

A voice assistant that listens and answers in Arabic, built from open components: **faster-whisper** turns speech into text, an LLM writes a short answer, **Piper** speaks it. It runs first on a laptop, then as services on Kubernetes (minikube with Helm), then on AKS.

**Status: M4 — four container images and one `docker compose up`.** Not on Kubernetes yet.

```
browser (push to talk) ──POST /api/turn──▶ gateway :8080 ──▶ stt      POST /v1/audio/transcriptions  (faster-whisper)
                                                     ├──▶ chat     POST /v1/chat/completions      (Ollama)
                                                     └──▶ tts      POST /v1/audio/speech          (Piper)
                     models job ──▶ volume `models` (read-only for stt and tts)
```

| Step | Component | Local | Planned on Azure |
|---|---|---|---|
| Speech to text | faster-whisper 1.2.1 (Whisper on CTranslate2), CPU, int8 | Whisper small (D16) | same container on AKS |
| Answer | any OpenAI-compatible endpoint | Ollama, `phi4-mini:3.8b` (D17) | Azure OpenAI through workload identity |
| Text to speech | Piper 1.8.0, Arabic voice `ar_JO-kareem-medium` | same | same container on AKS |

The speech services speak OpenAI's audio routes, so the gateway uses one `openai` client for all three steps and any of them can be replaced by a hosted service by changing a URL.

## Run it

Needs Docker with Compose, and on first use about 550 MB of model downloads, 2.5 GB for the chat model and a few minutes of image builds.

    docker compose build
    docker compose run --rm models
    docker compose up -d --wait
    docker exec voice-ollama ollama pull phi4-mini:3.8b

Open http://localhost:8080, hold the button (or the space bar), ask a question in Arabic, let go.

Without a browser: `curl -s -F file=@question.wav http://127.0.0.1:8080/api/turn | jq 'del(.audio)'`.

What the compose file starts:

| Service | Image | Port on 127.0.0.1 | Memory limit |
|---|---|---|---|
| `models` (runs once) | `voice-models:local` | — | 512 MB |
| `stt` | `voice-stt:local` | 8001 | 2048 MB |
| `tts` | `voice-tts:local` (the only image with Piper) | 8002 | 1024 MB |
| `gateway` | `voice-gateway:local` | 8080 | 256 MB |
| `ollama` | `ollama/ollama`, pinned by digest | 11434 | 4480 MB |

Our images run as a non-root user on a read-only filesystem and contain no model files. The `models` job downloads the models into a volume and checks every file against `models.lock.json` (repository revision and SHA-256); the speech services mount that volume read-only and do not start without their model. `STT_THREADS` (default 6) and `CHAT_MODEL` can be set in `.env`.

Base images are pinned by digest: `scripts/pin_images.py` moves them, `scripts/check_images.py` checks what was built.

## Develop without rebuilding images

    uv sync
    uv run python scripts/fetch_models.py stt-small tts-ar-kareem-medium
    docker compose up -d ollama

Then one terminal each (stop the compose services first: same ports):

    uv run uvicorn --factory voice.services.stt_app:create_app --port 8001
    uv run uvicorn --factory voice.services.tts_app:create_app --port 8002
    uv run uvicorn --factory voice.services.gateway_app:create_app --port 8080

## What is measured so far

- `scripts/roundtrip.py`: eight sentences spoken by Piper and transcribed by faster-whisper. A smoke test of the pipeline and its speed, not of recognition (synthetic speech, one voice).
- **Real speech (M3):** 20 recorded questions (14 Modern Standard Arabic, 6 Gulf dialect) and 40 sentences of FLEURS Arabic (CC BY 4.0), Whisper small against large-v3-turbo; small chat models on 24 Arabic questions with known answers; and a time budget per stage, measured through the services. The comparison and the choices: [docs/evidence/m3-summary.md](docs/evidence/m3-summary.md). Audio is not in the repository; `scripts/speech_set.py` rebuilds the sets.
- **Containers (M4):** the same turns through compose against the budget ([docs/evidence/m4-turns.md](docs/evidence/m4-turns.md)), what was built ([docs/evidence/m4-images.md](docs/evidence/m4-images.md)) and the image scans (`docs/evidence/m4-trivy-*.txt`).

Design choices and their reasons: [docs/decisions.md](docs/decisions.md).