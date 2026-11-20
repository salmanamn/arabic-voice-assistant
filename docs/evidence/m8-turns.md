# One turn through the services (AKS pods (1 × Standard_F8als_v6, 8 cores without SMT), namespace voice, 1 stt replica(s))

- Date: 2026-11-20 02:49 UTC; 20/20 turns of the `own` set after one warm-up turn
- Models: `stt-small` (3 threads) + `gpt-5.4-mini`
- Compared with `out/m5/turns-kube.json`: 2026-11-17 22:46 UTC, `stt-small` (3 threads) + `phi4-mini:3.8b`

| Stage | Budget p90 s | Before p50 s | Before p90 s | Now p50 s | Now p90 s | p90 change s | |
|---|---|---|---|---|---|---|---|
| stt | 2.5 | 2.66 | 2.80 | 1.28 | 1.36 | -1.44 | OK |
| chat | 3.5 | 2.32 | 5.57 | 1.41 | 1.90 | -3.67 | OK |
| tts | 0.8 | 0.30 | 0.95 | 0.17 | 0.26 | -0.69 | OK |
| other | 0.2 | 0.00 | 0.01 | 0.00 | 0.01 | +0.00 | OK |
| total | 7 | 5.19 | 9.71 | 2.90 | 3.34 | -6.37 | OK |

| Service | Peak memory MB | Before MB | Limit MB | Peak / limit |
|---|---|---|---|---|
| stt | 673 | 877 | 2048 | 33% |
| tts | 453 | 582 | 1024 | 44% |
| gateway | 94 | 75 | 256 | 37% |

Chat: Azure OpenAI gpt-5.4-mini 2026-03-17 (GlobalStandard, reasoning effort low) through the gateway workload identity; no Ollama in this release.
