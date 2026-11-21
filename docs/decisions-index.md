# Decisions index

Generated from the headings of [decisions.md](decisions.md) by `scripts/decisions_index.py`; don't edit it by
hand. `tests/unit/test_decisions.py` fails when this file and the headings disagree, or when a number is
missing or used twice.

60 decisions (D1–D60): 7 updated by a later one, 4 with a status of
their own (open questions, workarounds); the rest accepted as written.

| # | Decision | Status |
|---|---|---|
| [D1](decisions.md#d1--shape-one-turn-three-components) | Shape: one turn, three components | accepted |
| [D2](decisions.md#d2--speech-to-text-faster-whisper-whisper-small-to-start) | Speech to text: faster-whisper, Whisper small to start | accepted; updated by D16 |
| [D3](decisions.md#d3--text-to-speech-piper-voice-ar_jo-kareem-medium) | Text to speech: Piper, voice ar_JO-kareem-medium | accepted |
| [D4](decisions.md#d4--model-files-are-pinned-artifacts-outside-git-and-images) | Model files are pinned artifacts, outside git and images | accepted |
| [D5](decisions.md#d5--arabic-only) | Arabic only | accepted |
| [D6](decisions.md#d6--the-answer-any-openai-compatible-endpoint) | The answer: any OpenAI-compatible endpoint | accepted; updated by D17 |
| [D7](decisions.md#d7--configuration-from-environment-variables-only) | Configuration from environment variables only | accepted |
| [D8](decisions.md#d8--the-round-trip-is-a-smoke-test-not-an-accuracy-measure) | The round trip is a smoke test, not an accuracy measure | accepted |
| [D9](decisions.md#d9--one-dependency-group-per-image) | One dependency group per image | accepted |
| [D10](decisions.md#d10--three-services-on-openais-routes) | Three services on OpenAI's routes | accepted |
| [D11](decisions.md#d11--one-model-call-at-a-time-per-process-a-short-queue-then-503) | One model call at a time per process, a short queue, then 503 | accepted |
| [D12](decisions.md#d12--health-liveness-and-readiness-only-about-the-process-itself) | Health: liveness and readiness only about the process itself | accepted |
| [D13](decisions.md#d13--limits-errors-and-logs) | Limits, errors and logs | accepted |
| [D14](decisions.md#d14--m2-runs-as-processes-on-the-laptop-containers-come-in-m4) | M2 runs as processes on the laptop; containers come in M4 | superseded in M4: the services run in containers (D19–D21); the three-terminal way stays for development |
| [D15](decisions.md#d15--real-speech-test-sets-your-recordings-and-fleurs-audio-outside-git) | Real-speech test sets: your recordings and FLEURS, audio outside git | accepted |
| [D16](decisions.md#d16--speech-to-text-stt-small-updates-d2) | Speech to text: `stt-small` | accepted; updates D2 |
| [D17](decisions.md#d17--chat-model-on-the-laptop-phi4-mini38b-updates-d6) | Chat model on the laptop: `phi4-mini:3.8b` | accepted; updates D6 |
| [D18](decisions.md#d18--time-budget-per-stage) | Time budget per stage | accepted |
| [D19](decisions.md#d19--images-one-dockerfile-four-targets-nothing-in-them-that-the-service-does-not-need) | Images: one Dockerfile, four targets, nothing in them that the service does not need | accepted |
| [D20](decisions.md#d20--models-come-from-a-volume-filled-and-checked-by-a-job) | Models come from a volume, filled and checked by a job | accepted |
| [D21](decisions.md#d21--compose-runs-all-four-services) | Compose runs all four services | accepted |
| [D22](decisions.md#d22--scanning-and-pins) | Scanning and pins | accepted |
| [D23](decisions.md#d23--registry-github-container-registry-for-what-ci-builds-azure-container-registry-only-as-the-clusters-copy) | Registry: GitHub Container Registry for what CI builds; Azure Container Registry only as the cluster's copy | open: the licence is for the owner to decide; until then `stt` and `tts` are not published (D37, D38); updated by D38 |
| [D24](decisions.md#d24--speech-models-on-kubernetes-a-job-writes-the-volume-every-pod-checks-it) | Speech models on Kubernetes: a Job writes the volume, every pod checks it | accepted |
| [D25](decisions.md#d25--the-chat-model-pulled-by-a-job-pinned-by-id-loaded-before-ollama-is-ready) | The chat model: pulled by a Job, pinned by id, loaded before Ollama is ready | accepted |
| [D26](decisions.md#d26--requests-and-limits) | Requests and limits | accepted |
| [D27](decisions.md#d27--the-gateway-opens-a-new-connection-for-every-speech-call) | The gateway opens a new connection for every speech call | accepted |
| [D28](decisions.md#d28--autoscaling-stt-on-cpu) | Autoscaling `stt` on CPU | accepted |
| [D29](decisions.md#d29--network-everything-denied-then-the-flows-a-turn-needs) | Network: everything denied, then the flows a turn needs | accepted; updated by D44 |
| [D30](decisions.md#d30--restricted-pod-security-standard-ollama-included) | Restricted Pod Security Standard, Ollama included | accepted |
| [D31](decisions.md#d31--stopping-drain-then-exit-within-a-bounded-time) | Stopping: drain, then exit, within a bounded time | accepted |
| [D32](decisions.md#d32--the-chart) | The chart | accepted; updated by D38 |
| [D33](decisions.md#d33--model-downloads-resume-with-a-fresh-url-each-attempt) | Model downloads resume, with a fresh URL each attempt | accepted |
| [D34](decisions.md#d34--the-chart-is-tested-on-a-cluster-in-ci) | The chart is tested on a cluster in CI | accepted |
| [D35](decisions.md#d35--known-bad-changes-must-fail) | Known-bad changes must fail | accepted |
| [D36](decisions.md#d36--ci-one-workflow-required-checks-pinned-tools) | CI: one workflow, required checks, pinned tools | accepted |
| [D37](decisions.md#d37--ghcr-the-gateway-and-the-models-job-from-main-only) | GHCR: the gateway and the models job, from `main` only | accepted |
| [D38](decisions.md#d38--images-on-aks-cis-tested-bytes-by-digest-from-the-stacks-acr-updates-d23-and-d32) | Images on AKS: CI's tested bytes, by digest, from the stack's ACR | accepted; updates D23, D32 |
| [D39](decisions.md#d39--floci-az-stays-at-0160) | floci-az stays at 0.16.0 | accepted |
| [D40](decisions.md#d40--terraform-layout-the-same-as-ticket-triage-agent) | Terraform layout: the same as ticket-triage-agent | accepted; updated by D53 |
| [D41](decisions.md#d41--the-cluster) | The cluster | accepted; updated by D53 |
| [D42](decisions.md#d42--one-node-standard_f8als_v6) | One node: Standard_F8als_v6 | accepted |
| [D43](decisions.md#d43--storage-one-node-one-readwriteonce-azure-disk) | Storage: one node, one ReadWriteOnce Azure Disk | accepted |
| [D44](decisions.md#d44--egress-by-host-name-cilium-fqdn-policies-not-a-firewall-updates-d29) | Egress by host name: Cilium FQDN policies, not a firewall | accepted; updates D29 |
| [D45](decisions.md#d45--the-answer-on-azure-azure-openai-with-the-gateways-workload-identity) | The answer on Azure: Azure OpenAI with the gateway's workload identity | accepted |
| [D46](decisions.md#d46--roles) | Roles | accepted |
| [D47](decisions.md#d47--diagnostics) | Diagnostics | accepted |
| [D48](decisions.md#d48--the-infrastructure-gate-in-ci) | The infrastructure gate in CI | accepted |
| [D49](decisions.md#d49--deploying-to-aks-deployyml) | Deploying to AKS: deploy.yml | accepted |
| [D50](decisions.md#d50--cost-of-a-session) | Cost of a session | accepted |
| [D51](decisions.md#d51--deploy-chart-signs-the-azure-cli-in-again-before-each-step-that-needs-a-new-entra-id-token) | deploy-chart signs the Azure CLI in again before each step that needs a new Entra ID token | accepted |
| [D52](decisions.md#d52--the-operators-kubectl-reaches-one-namespace) | The operator's kubectl reaches one namespace | accepted |
| [D53](decisions.md#d53--aks-136-from-137-localdns-takes-dns-away-from-coredns-m8-first-evening-updates-d40-d41) | AKS 1.36: from 1.37 LocalDNS takes DNS away from CoreDNS (M8, first evening) | workaround: back to 1.37 once azurerm can set the LocalDNS profile of the node pool, or with DNS rules that reach the node (Project 7); updates D40, D41 |
| [D54](decisions.md#d54--the-first-deploy-on-aks-m8) | The first deploy on AKS (M8) | accepted |
| [D55](decisions.md#d55--measured-on-aks-m8) | Measured on AKS (M8) | accepted |
| [D56](decisions.md#d56--identity-and-access-as-they-behaved-m8) | Identity and access, as they behaved (M8) | accepted |
| [D57](decisions.md#d57--what-the-session-cost-m8) | What the session cost (M8) | accepted |
| [D58](decisions.md#d58--closing-project-4-a-readme-of-what-was-measured-and-an-index-of-the-decisions-m9) | Closing Project 4: a README of what was measured, and an index of the decisions (M9) | accepted |
| [D59](decisions.md#d59--azure-ai-speech-as-an-optional-backend-of-the-gateway-keyless-m9) | Azure AI Speech as an optional backend of the gateway, keyless (M9) | optional: built for the comparison evening (M9 Part C); M9 closes without it |
| [D60](decisions.md#d60--azure-ai-speech-against-faster-whisper-and-piper-on-aks-measured-m9) | Azure AI Speech against faster-whisper and Piper on AKS, measured (M9) | accepted |
