# Decisions

## D1 — Shape: one turn, three components
- A turn is: the user speaks a question, the assistant answers aloud. Push-to-talk, one utterance in and one out. No barge-in, no streaming audio in either direction, no conversation memory yet.
- Three components with one job each: speech to text, the answer (an LLM), text to speech. In M1 they run in one Python process on the laptop to prove the models and measure them. From M2 each is a service, so that on Kubernetes they scale and fail separately.
- Same rule as the earlier projects: the code that runs on the laptop is the code that runs in a container and on AKS; only configuration differs (D7).

## D2 — Speech to text: faster-whisper, Whisper small to start
- faster-whisper 1.2.1 (Whisper on CTranslate2 4.x), CPU, weights quantised to int8 at load. No GPU in the lab or on the planned AKS nodes.
- Model for M1: **Whisper small** (`Systran/faster-whisper-small`). Whisper pads every utterance to a 30-second window, so recognition time is nearly constant per utterance and is set by the encoder size. small keeps a turn interactive on a laptop CPU. `large-v3-turbo` is in the catalog for comparison; the choice between them is made on real speech (accuracy) against the time measured here, not on the synthetic round trip (D8). Chosen on real speech in M3: D16.
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
- Local model to start: `phi4-mini:3.8b` on Ollama 0.40.15, CPU (MIT, no thinking mode, 2.5 GB, already used in the ticket-triage lab). Its Arabic answer quality is not measured yet; the model is one environment variable (`CHAT_MODEL`), and the comparison with other small models belongs to the Arabic evaluation milestone. Chosen in M3: D17.
- System prompt in Arabic: answer only in Modern Standard Arabic, one or two short sentences, nothing a voice cannot read. Temperature 0.2, at most 160 output tokens. The turn script reports the share of Arabic letters in the answer, because answering in another language is a known failure of small models.

## D7 — Configuration from environment variables only
- `src/voice/settings.py` reads everything from the environment; the defaults are the laptop values (`MODELS_DIR=models`, `STT_MODEL`, `OPENAI_BASE_URL=http://127.0.0.1:11434/v1`, ...). No configuration files, no values in code paths.
- Recognition threads default to the **physical cores** among the CPUs the process may run on (its CPU affinity), capped at 8; `STT_THREADS` overrides. Hyper-threads of one core share its arithmetic units, so a second Whisper thread on the same core only adds contention: on the i7-9750H (6 cores, 12 CPUs) Whisper small took 1.78 s on 6 threads and 4.32 s on 8 for the same 3.2 s utterance. Changed in M3; until then the default was the logical CPUs capped at 8.
- Cores are counted from `/sys/devices/system/cpu/cpu*/topology/core_cpus_list` (older kernels: `thread_siblings_list`): CPUs with the same list share a core. Without those files every CPU counts as a core.
- In a container this follows CPU pinning (cpuset), not CPU limits (CFS quota): a pod limited to 2 CPUs on a 16-core node still sees 16 CPUs. The Helm chart (M5) therefore sets `STT_THREADS` to the pod's CPU request.

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

## D15 — Real-speech test sets: your recordings and FLEURS, audio outside git
- **own** (`eval/speech/own.jsonl`): 20 prompts read by Salman into his laptop microphone with Windows Sound Recorder — 14 in Modern Standard Arabic (questions an assistant gets: places in Bahrain, a date and time, numbers, a request) and 6 in Gulf dialect. This is the product's case: short questions, one speaker, a laptop microphone. The model choices (D16, D17) are made on it.
- **fleurs**: the first 40 sentences (lowest sentence id first, one recording each, at most 20 s) of the `ar_eg` test split of Google's FLEURS (`google/fleurs` on Hugging Face, CC BY 4.0: use with attribution). Read Wikipedia sentences in Modern Standard Arabic by several Egyptian speakers: longer and harder than a voice question, and other voices than the developer's. Reported next to own, not used to choose.
- Common Voice Arabic was not used: since October 2025 it is only on the Mozilla Data Collective, behind an account and terms that forbid re-sharing. FLEURS needs neither.
- Audio is not committed (`data/` is gitignored): a public repository is no place for the developer's voice, and FLEURS stays with its publisher. `data/speech/<set>/manifest.jsonl` records reference, length and SHA-256 of every file; `scripts/speech_set.py status` checks the files against it. The prompts and the scripts that rebuild both sets are committed.
- Scoring is D8's: CER without spaces and WER after `voice.textnorm.normalize`. Limits of that: numbers spoken as words against digits in the reference count as errors, and dialect has no single spelling (the own references give one), so Gulf WER overstates the errors.
- Six utterances per style is enough to see a large gap between MSA and dialect, not a small one.

## D16 — Speech to text: `stt-small`
- Candidates: Whisper small and large-v3-turbo (D2), int8, beam 5, threads by D7, measured by `scripts/eval_stt.py` on both sets (D15).
- Rule (`voice.quality.choose_stt`): a model is eligible when its p90 time per utterance on the own set is within the speech-to-text budget (2.5 s, D18). Among eligible models the lowest own-set CER wins; a CER less than one point lower than a faster model's does not count (noise on 20 utterances). If no model is within budget, the fastest is chosen and the budget is reported as missed.
- Result: own-set CER 10.1% at p90 1.96 s, within the 2.5 s budget; over budget: stt-turbo p90 8.99 s. Numbers: `docs/evidence/m3-summary.md` and `m3-stt-*.md`.
- The chosen model is the `STT_MODEL` default in `settings.py`; the other stays in the catalog and the lock.

## D17 — Chat model on the laptop: `phi4-mini:3.8b`
- Candidates, all through Ollama 0.40.15 on CPU, one loaded at a time: `phi4-mini:3.8b` (MIT, the M1 start), `gemma3:4b` (Gemma terms, 140 languages, no thinking mode), `qwen3.5:4b` (Apache 2.0; thinks by default, run with thinking off), `command-r7b-arabic:7b` (Cohere's Arabic-tuned 7B, CC BY-NC 4.0: fine for this non-commercial lab, not for a product), optionally `gemma4:e2b` (Apache 2.0; Ollama's default tag is 7.2 GB, over the memory budget before measuring).
- Thinking models get `CHAT_REASONING_EFFORT=none`: `voice.llm.Assistant` then keeps the classic request (temperature, `max_tokens`) and adds `reasoning_effort: "none"`, which Ollama's `/v1` maps to thinking off. A voice turn cannot wait for a hidden reasoning pass, and thinking spends the 160-token limit before the answer.
- Test: `eval/qa.jsonl`, 24 Arabic questions with known answers (Bahrain and Gulf facts, world facts, numbers and arithmetic), asked once each with the product's own request (system prompt, temperature 0.2, 160 tokens) by `scripts/eval_chat.py`. Correct = an accepted answer appears as whole words after normalisation; Arabic = at least 90 % Arabic letters; memory = Ollama's resident size of the loaded model.
- Rule (`voice.quality.choose_chat`): eligible when every answer arrived, at least 95 % of answers are Arabic, the model fits in 7 GB, and its warm p90 is within the chat budget (3.5 s, D18). Most correct answers wins, then the faster p50. If none is within the time budget, the most correct one that fits in memory is chosen and the budget is reported as missed. Below 80 % correct the model is called what it is: a stand-in for development until Azure OpenAI (M8) answers on AKS.
- Result: 54% correct, 96% Arabic, p90 2.38 s, 3.1 GB; below the 80% correctness bar: a lab stand-in until Azure OpenAI (M8); ruled out: command-r7b-arabic:7b (p90 33.12 s), gemma3:4b (p90 5.34 s), qwen3.5:4b@none (p90 8.31 s). Numbers: `docs/evidence/m3-summary.md` and `m3-chat.md`.
- 24 questions measure gross differences (the capital of Bahrain, simple arithmetic, staying in Arabic), not general quality. The questions are a tuning set from now on: a later prompt change is checked against it, and any claim about held-out quality needs new questions.

## D18 — Time budget per stage
- Budget for one turn, warm, on the laptop, from the end of the question to the start of the answer audio, as p90 over the own set: speech to text 2.5 s, chat 3.5 s, text to speech 0.8 s, everything else (gateway, HTTP hops, base64) 0.2 s; **total 7 s**. Seven seconds is slow for a conversation but usable for push-to-talk questions on a CPU; the stage split shows where time goes when it is missed. Chat memory budget 7 GB, so the speech services and Windows still fit in 16 GB.
- Measured by `scripts/measure_turns.py`: every own recording through the running gateway, after one warm-up turn, with the chosen models. Result: p50 4.49 s / p90 6.84 s against 7 s; over: chat p90 3.61 s > 3.5 s (`stt-small` + `phi4-mini:3.8b`, 2026-11-16 15:48 UTC).
- Cold start is outside the budget and only reported: loading a chat model takes up to a minute on this laptop. Ollama keeps the model loaded for 30 minutes (`OLLAMA_KEEP_ALIVE`); on Kubernetes the speech pods load their model before they report ready (D12).
- The numbers carry into M5: CPU requests from the threads that met the budget, memory requests/limits from the peak resident memory `measure_turns.py` reports per service (with headroom), and the startup probe from the model load times.