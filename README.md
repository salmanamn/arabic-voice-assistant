# arabic-voice-assistant

A voice assistant that listens and answers in Arabic, built from open components: **faster-whisper** turns speech into text, an LLM writes a short answer, **Piper** speaks it. It runs first on a laptop, then as services on Kubernetes (minikube with Helm), then on AKS.

**Status: M1 — the three components work together on the laptop.** No services, containers or Kubernetes yet.

| Step | Component | Local | Planned on Azure |
|---|---|---|---|
| Speech to text | faster-whisper 1.2.1 (Whisper on CTranslate2), CPU, int8 | Whisper small | same container on AKS |
| Answer | any OpenAI-compatible endpoint | Ollama, `phi4-mini:3.8b` | Azure OpenAI through workload identity |
| Text to speech | Piper 1.8.0, Arabic voice `ar_JO-kareem-medium` | same | same container on AKS |

## Run it

Needs uv, Docker and about 3.5 GB of downloads (models and packages) on first use.

    uv sync
    uv run python scripts/fetch_models.py stt-small tts-ar-kareem-medium
    uv run python scripts/roundtrip.py                       # text -> speech -> text, 8 Arabic sentences
    docker compose up -d && docker exec voice-ollama ollama pull phi4-mini:3.8b
    uv run python scripts/turn.py "ما هي عاصمة مملكة البحرين؟"   # question -> out/turn-reply.wav

Model files are not in this repository. `models.lock.json` pins each one to a repository revision and the SHA-256 of every file; `scripts/fetch_models.py --verify` checks what is on disk.

## What is measured so far

`scripts/roundtrip.py` speaks eight Arabic sentences with Piper and transcribes them with faster-whisper: see [docs/evidence](docs/evidence). That proves the pipeline and gives its speed on one machine. It is clean synthetic speech from one voice, so it says little about recognising real speakers; that measurement comes with a real-speech test set.

Design choices and their reasons: [docs/decisions.md](docs/decisions.md).