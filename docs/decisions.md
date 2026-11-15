# Decisions

## D1 — Shape: one turn, three components
- A turn is: the user speaks a question, the assistant answers aloud. Push-to-talk, one utterance in and one out. No barge-in, no streaming audio in either direction, no conversation memory yet.
- Three components with one job each: speech to text, the answer (an LLM), text to speech. In M1 they run in one Python process on the laptop to prove the models and measure them. From M2 each is a service, so that on Kubernetes they scale and fail separately.
- Same rule as the earlier projects: the code that runs on the laptop is the code that runs in a container and on AKS; only configuration differs (D7).

## D2 — Speech to text: faster-whisper, Whisper small to start
- faster-whisper 1.2.1 (Whisper on CTranslate2 4.x), CPU, weights quantised to int8 at load. No GPU in the lab or on the planned AKS nodes.
- Model for M1: **Whisper small** (`Systran/faster-whisper-small`). Whisper pads every utterance to a 30-second window, so recognition time is nearly constant per utterance and is set by the encoder size. small keeps a turn interactive on a laptop CPU. `large-v3-turbo` is in the catalog for comparison; the choice between them is made on real speech (accuracy) against the time measured here, not on the synthetic round trip (D8).
- Decoding: language fixed to Arabic (D5), beam 5, voice-activity filter on (silence is removed before recognition; Whisper invents text for non-speech), no conditioning on previous text (utterances are independent).
- The model directory must contain `model.bin`, `config.json` and `tokenizer.json`; the wrapper checks this before loading, because faster-whisper would otherwise try to download a missing tokenizer from the Hugging Face Hub at run time.
- `av` (PyAV) is pinned below 19: faster-whisper 1.2.1 calls `av.open(metadata_errors=...)`, an argument PyAV 19 removed; with PyAV 19 every file transcription fails with a `TypeError`. Remove the pin when faster-whisper supports PyAV 19.

## D3 — Text to speech: Piper, voice ar_JO-kareem-medium
- piper-tts 1.8.0 (the maintained `OHF-Voice/piper1-gpl`; the original MIT `rhasspy/piper` is archived). A VITS voice on ONNX Runtime: about 0.07 seconds of CPU per second of speech on two cores, roughly 200 MB of memory.
- Voice: `ar_JO-kareem-medium` from `rhasspy/piper-voices`, 22.05 kHz, one speaker. Written Arabic normally has no short vowels; Piper restores them before phonemising (a libtashkeel model inside the piper-tts package, applied automatically for Arabic voices). Its mistakes are audible as wrong vowels.
- Licence boundary: piper-tts is GPL-3.0-or-later. Text to speech therefore becomes its own service and image (M2, M4), called over HTTP; the other components do not import Piper. In M1 the scripts import it directly.
- The assistant's text is cleaned before synthesis (`clean_for_speech`): markdown, links, list markers and emoji are removed, because the voice would read or stumble over them.

## D4 — Model files are pinned artifacts, outside git and images
- Models are fetched by `scripts/fetch_models.py` into `models/` (gitignored). `src/voice/modelstore.py` holds the catalog (which repository, which files); `models.lock.json` (committed) holds, per model, the repository revision and the SHA-256 and size of every file.
- First fetch of a model: resolves the newest revision and writes the lock entry (trust on first use). Every later fetch, on any machine: downloads that revision, and fails if a file differs from the lock. `--verify` compares what is on disk; `--update NAME` moves the lock on purpose.
- Why a lock and not only a revision: the SHA-256 lets a container or an init job check its model files without calling the hub, and it detects a changed file on disk.
- Licences: the Whisper conversions are MIT. The voice's model card names no licence and points to its dataset repository. Until that is clear the voice is not copied into a public image or redistributed; it is downloaded from its publisher at deploy time.

## D5 — Arabic only
- Input language is fixed to Arabic for recognition: language detection on a two-second utterance is unreliable and costs time. Answers are requested in Modern Standard Arabic.
- Not handled: dialects are recognised as well as Whisper happens to, mixed Arabic and English is not tested, and digits and Latin words in answers are read by Piper's rules. Each needs real-speech measurements before it is worth designing for.

## D6 — The answer: any OpenAI-compatible endpoint
- One `openai` SDK client (as in ticket-triage-agent D3). Locally Ollama's `/v1`; on Azure the Azure OpenAI v1 endpoint. `CHAT_REASONING_EFFORT` switches the request to the shape reasoning models need (`reasoning_effort` + `max_completion_tokens`, no `temperature`); empty locally.
- Local model to start: `phi4-mini:3.8b` on Ollama 0.40.15, CPU (MIT, no thinking mode, 2.5 GB, already used in the ticket-triage lab). Its Arabic answer quality is not measured yet; the model is one environment variable (`CHAT_MODEL`), and the comparison with other small models belongs to the Arabic evaluation milestone.
- System prompt in Arabic: answer only in Modern Standard Arabic, one or two short sentences, nothing a voice cannot read. Temperature 0.2, at most 160 output tokens. The turn script reports the share of Arabic letters in the answer, because answering in another language is a known failure of small models.

## D7 — Configuration from environment variables only
- `src/voice/settings.py` reads everything from the environment; the defaults are the laptop values (`MODELS_DIR=models`, `STT_MODEL=stt-small`, `OPENAI_BASE_URL=http://127.0.0.1:11434/v1`, ...). No configuration files, no values in code paths.
- Recognition threads default to the CPUs the process may use, capped at 8 (`STT_THREADS` overrides). In a container this follows CPU pinning, not CPU limits, so the Kubernetes manifests will set it explicitly.

## D8 — The round trip is a smoke test, not an accuracy measure
- `scripts/roundtrip.py`: eight Arabic sentences (`eval/roundtrip.jsonl`) go text → Piper → WAV → faster-whisper → text and are scored against the original after normalisation (`voice.textnorm.normalize`: diacritics and punctuation removed, alef, ya and ta marbuta forms unified). Character error rate is counted without spaces; word error rate on whitespace-separated words.
- It proves that both models load, agree on audio format and understand each other, and it measures time per sentence on this machine. It does not measure recognition of real speakers: the audio is clean, synthetic and from one voice.
- Gates: corpus CER ≤ 10 %, corpus WER ≤ 20 %, no sentence above 30 % CER, and two seconds of silence must transcribe to nothing. When they were set, Whisper small scored 3.3 % CER and 8 % WER; Whisper tiny scored 6.5 % and 30 % and fails. The gate catches a broken pipeline or a much weaker model, nothing finer.
- Piper adds random noise to every synthesis. The script fixes ONNX Runtime's seed, so the audio and the result repeat on the same machine.

## D9 — One dependency group per future image
- `pyproject.toml` keeps faster-whisper (`stt`), Piper (`tts`) and the hub client (`models`) in separate dependency groups, all installed by default on the laptop. The speech-to-text image will install only `stt`, the text-to-speech image only `tts` (D3), and neither needs the hub client at run time.

## D10 — Three services on OpenAI's routes
- `stt` serves `POST /v1/audio/transcriptions` (multipart `file`, `model`, `language`, `response_format` json|text → `{"text", "duration"}`), `tts` serves `POST /v1/audio/speech` (JSON `input`, `model`, `voice`, `response_format` wav → WAV bytes), the gateway serves `POST /api/turn` (multipart `file` → `{"heard", "answer", "audio", "timings"}`) and the push-to-talk page at `/`.
- Speaking OpenAI's shapes means the gateway needs one client library for all three steps, and a hosted service (Azure OpenAI's audio routes, Azure Speech behind an adapter) can replace a pod by changing `STT_URL`, `TTS_URL` or `OPENAI_BASE_URL`. Only what this project uses is implemented: `model` and `voice` are accepted and ignored (one model per process), other languages, formats and speeds are refused with 400.
- Only the `tts` process imports Piper (GPL, D3); the gateway reaches it over HTTP.
- The gateway returns the answer's audio as base64 inside the JSON (about 200 KB per answer) instead of streaming: one request per turn, simple to test. Streaming belongs with lower-latency work, not with this milestone.

## D11 — One model call at a time per process, a short queue, then 503
- A Whisper or Piper model uses all the CPU threads it is given, so two calls at once in one process only slow each other down. Each speech service runs one call at a time (`Worker`, off the event loop) and lets at most `MAX_WAITING` (4) requests wait; the next one gets 503 `busy` at once instead of a timeout minutes later.
- One request is one job (decode, length check, recognition together), so a full queue gives 503 and never a misleading 400.
- More capacity is more processes (replicas on Kubernetes), not more threads in one.

## D12 — Health: liveness and readiness only about the process itself
- `/healthz`: the process answers. `/readyz`: the model is loaded. Models load before the port opens (FastAPI lifespan), so a starting pod refuses connections until it can work: on Kubernetes that is a startup probe plus a readiness probe.
- The gateway's readiness does not check the speech services or the chat endpoint: a dependency being down would otherwise take the gateway out of the load balancer too, and the user would get a connection error instead of `503 stt_unavailable`. Each step's failure is named in the error code (`stt_`, `chat_`, `tts_` + `unavailable` | `busy` | `failed`).

## D13 — Limits, errors and logs
- Limits (environment variables): recording ≤ 2 MiB (`MAX_UPLOAD_BYTES`, checked by the gateway and again by `stt`), ≤ 20 s after decoding (`MAX_AUDIO_SECONDS`; the decoded length, so a small compressed file cannot carry an hour of audio), answer to speak ≤ 600 characters (`MAX_SPEECH_CHARS`; the gateway cuts a longer answer at a word boundary). The page stops recording at 15 s.
- Error bodies are OpenAI-style `{"error": {"code", "message"}}` with fixed messages; FastAPI's validation errors are replaced by a 400 that names the fields only (its default 422 echoes the submitted values). As in ticket-triage-agent, errors never echo input.
- Logs carry lengths and times only (`heard 28 chars, answered 31 chars, {'stt': 2.07, ...}`): what the user said and heard stays out of them. A unit test checks this.

## D14 — M2 runs as processes on the laptop; containers come in M4
- The milestone plan had `docker compose up` running everything in M2. That needs images, which are M4's subject (non-root, read-only, no models inside). M2 runs the three services with `uv run uvicorn` in three terminals; only Ollama is a container. M4 adds the images and moves all four into compose.
- Ports: `stt` 8001, `tts` 8002, gateway 8080, all on 127.0.0.1. The page needs a secure context for the microphone; `http://localhost` is one.