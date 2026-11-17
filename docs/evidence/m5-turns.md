# One turn through the services (minikube pods, namespace voice, 1 stt replica(s))

- Date: 2026-11-17 22:46 UTC; 20/20 turns of the `own` set after one warm-up turn
- Models: `stt-small` (3 threads) + `phi4-mini:3.8b`
- Compared with `out/m4/turns-compose.json`: 2026-11-16 22:16 UTC, `stt-small` (6 threads) + `phi4-mini:3.8b`

| Stage | Budget p90 s | Before p50 s | Before p90 s | Now p50 s | Now p90 s | p90 change s | |
|---|---|---|---|---|---|---|---|
| stt | 2.5 | 2.30 | 7.38 | 2.66 | 2.80 | -4.58 | OVER |
| chat | 3.5 | 2.13 | 5.18 | 2.32 | 5.57 | +0.39 | OVER |
| tts | 0.8 | 0.34 | 1.04 | 0.30 | 0.95 | -0.09 | OVER |
| other | 0.2 | 0.00 | 0.00 | 0.00 | 0.01 | +0.01 | OK |
| total | 7 | 5.53 | 14.08 | 5.19 | 9.71 | -4.37 | OVER |

| Service | Peak memory MB | Before MB | Limit MB | Peak / limit |
|---|---|---|---|---|
| stt | 877 | 883 | 2048 | 43% |
| tts | 582 | 574 | 1024 | 57% |
| gateway | 75 | 78 | 256 | 29% |

Ollama: phi4-mini:3.8b 3.11 GB.
