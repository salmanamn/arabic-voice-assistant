# arabic-voice-assistant

A voice assistant that listens and answers in Arabic, built from open components: **faster-whisper** turns speech into text, an LLM writes a short answer, **Piper** speaks it. It runs on a laptop, as services on Kubernetes (minikube with Helm), and on AKS.

**Status: M8 — deployed to AKS once, measured, destroyed.** CI applied the Azure stack (AKS with Entra ID, Azure RBAC and workload identity, ACR, Azure OpenAI) from an approved, exact plan, installed the chart with CI's tested images by digest, and ran a spoken turn and every network flow on the cluster. On one 8-core node a turn took <fill> s at p90 (budget 7 s; minikube 9.71 s), with the answer from gpt-5.4-mini through the gateway's workload identity and egress allowed by host name only. The stack was destroyed the same evening; what it cost is in [docs/evidence/m8-cost.txt](docs/evidence/m8-cost.txt).

```
browser (push to talk) ──POST /api/turn──▶ gateway :8080 ──▶ stt      POST /v1/audio/transcriptions  (faster-whisper)
                                                     ├──▶ chat     POST /v1/chat/completions      (Ollama)
                                                     └──▶ tts      POST /v1/audio/speech          (Piper)
                     models job ──▶ volume `models` (read-only for stt and tts)
```

| Step | Component | Local | Planned on Azure |
|---|---|---|---|
| Speech to text | faster-whisper 1.2.1 (Whisper on CTranslate2), CPU, int8 | Whisper small (D16) | same container on AKS |
| Answer | any OpenAI-compatible endpoint | Ollama, `phi4-mini:3.8b` (D17) | Azure OpenAI `gpt-5.4-mini` through workload identity (D45) |
| Text to speech | Piper 1.8.0, Arabic voice `ar_JO-kareem-medium` | same | same container on AKS |

The speech services speak OpenAI's audio routes, so the gateway uses one `openai` client for all three steps and any of them can be replaced by a hosted service by changing a URL.

## Run it

Needs Docker with Compose, and on first use about 550 MB of model downloads, 2.5 GB for the chat model and a few minutes of image builds.

    docker compose build
    docker compose run --rm models
    docker compose up -d ollama
    docker exec voice-ollama ollama pull phi4-mini:3.8b
    docker compose up -d --wait

`up --wait` returns once Ollama has the chat model in memory (its health check loads it, a few minutes on a laptop CPU).

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

## Run it on minikube

Needs minikube with Calico and metrics-server, kubectl and Helm 4; the images built by `docker compose build`; compose stopped (same memory, same port 8080). The values in `deploy/charts/voice/values.yaml` are for a 12-CPU, 10 GiB minikube; `ollama.modelId` pins the chat model (the ID column of `ollama list`).

    minikube start --driver=docker --container-runtime=containerd --cpus=12 --memory=10g --cni=calico --addons=metrics-server
    for i in stt tts gateway models; do minikube image load voice-$i:local; done
    kubectl apply -f deploy/namespace.yaml
    helm install voice deploy/charts/voice -n voice --wait --timeout 30m
    helm test voice -n voice --logs
    kubectl -n voice port-forward svc/gateway 8080:8080

Then http://localhost:8080 as above. The first install downloads both models into the cluster (a Job each). What the chart adds to compose: a startup, readiness and liveness probe per service, CPU and memory requests, an autoscaler for `stt` (1–2 replicas), every pod non-root on a read-only filesystem under the restricted Pod Security Standard, and network policies that deny everything a turn does not need (`scripts/check_netpol.py` checks them from inside the pods).

## Run it on AKS

Terraform in `infra/` (modules `aks`, `registry`, `openai`, composed by `stack`; `envs/local` for the floci-az emulator, `envs/azure` with remote state). Everything goes through `deploy.yml` with GitHub OIDC; nothing is applied from the laptop:

    ./scripts/ci-deploy.sh apply          # plan → policy gate → approve → apply that exact plan
    ./scripts/ci-deploy.sh deploy-chart   # CI's tested images → ACR, helm upgrade, helm test, every network flow
    ./scripts/ci-deploy.sh destroy        # the same evening

One `Standard_F8als_v6` node, about $3 for a 4-hour session (D50). Your own access: `./scripts/aks-deploy.sh settings && ./scripts/aks-deploy.sh credentials`, then `kubectl -n voice port-forward svc/gateway 8080:8080`.

The first session (M8) step by step, with what each command printed: [docs/evidence/m8-session.md](docs/evidence/m8-session.md). As the operator you are admin of namespace `voice` only ([docs/evidence/m8-access.txt](docs/evidence/m8-access.txt)); `scripts/cost.sh <date>` reads what a session cost the day after.

## CI

`.github/workflows/ci.yml` runs on every pull request and push to `main`, and weekly. Required before a merge:
- `lint`
- `unit`
- `tests-must-fail`: 23 known-bad code changes must fail the tests
- `chart`: Conftest on four renderings of the chart; 30 known-bad chart changes must be denied
- `iac-static`: fmt, validate, Checkov, policy tests
- `iac-plan`: the full-stack plan against floci-az, Conftest, 24 known-bad plans must be denied
- `images`: build, image rules, Trivy (no fixable High/Critical)
- `e2e`: k3s on the runner, the chart with Whisper tiny and a fixed-answer chat stand-in, `helm test`, every network flow

On `main`, `publish` pushes `ghcr.io/salmanamn/voice-gateway` and `voice-models`; the weekly run rescans `main` and reports base-image tags that have moved. The speech-to-text and text-to-speech images are not published yet: they carry GPL code and the licence is still open (D23).

Locally: `uv run python scripts/tests_must_fail.py`, and with Helm and Conftest (`./scripts/ci-tools.sh helm conftest`) `python3 scripts/chart_must_fail.py`.

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
- **Kubernetes (M5):** a turn on minikube against the budget and against compose ([docs/evidence/m5-turns.md](docs/evidence/m5-turns.md)), the network policies flow by flow ([docs/evidence/m5-netpol.md](docs/evidence/m5-netpol.md)), the autoscaler under load ([docs/evidence/m5-hpa.md](docs/evidence/m5-hpa.md)), `helm test` ([docs/evidence/m5-helm-test.txt](docs/evidence/m5-helm-test.txt)), Ollama's cold load ([docs/evidence/m5-ollama-load.md](docs/evidence/m5-ollama-load.md)) and how the services stop ([docs/evidence/m5-stop.md](docs/evidence/m5-stop.md)).
- **AKS (M8):** a turn against the budget and against minikube ([docs/evidence/m8-turns.md](docs/evidence/m8-turns.md)), the autoscaler on 8 cores ([docs/evidence/m8-hpa.md](docs/evidence/m8-hpa.md)), every network flow with Cilium FQDN policies ([docs/evidence/m8-netpol.md](docs/evidence/m8-netpol.md), [docs/evidence/m8-fqdn.txt](docs/evidence/m8-fqdn.txt)), workload identity ([docs/evidence/m8-identity.txt](docs/evidence/m8-identity.txt)), the audit and request logs in the platform workspace ([docs/evidence/m8-logs.txt](docs/evidence/m8-logs.txt)) and the cost ([docs/evidence/m8-cost.txt](docs/evidence/m8-cost.txt)).

Design choices and their reasons: [docs/decisions.md](docs/decisions.md).
