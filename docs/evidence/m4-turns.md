# One turn through the services (compose containers)

- Date: 2026-11-16 18:26 UTC; 19/20 turns of the `own` set after one warm-up turn
- Models: `stt-small` (6 threads) + `phi4-mini:3.8b`
- Compared with `out/m3/turns.json`: 2026-11-16 15:48 UTC, `stt-small` (6 threads) + `phi4-mini:3.8b`

| Stage | Budget p90 s | Before p50 s | Before p90 s | Now p50 s | Now p90 s | p90 change s | |
|---|---|---|---|---|---|---|---|
| stt | 2.5 | 2.06 | 2.33 | 2.01 | 2.29 | -0.04 | OK |
| chat | 3.5 | 1.72 | 3.61 | 1.99 | 3.33 | -0.28 | OK |
| tts | 0.8 | 0.26 | 0.74 | 0.29 | 0.68 | -0.06 | OK |
| other | 0.2 | 0.00 | 0.00 | 0.00 | 0.01 | +0.01 | OK |
| total | 7 | 4.49 | 6.84 | 4.40 | 5.86 | -0.98 | OK |

| Service | Peak memory MB | Before MB | Limit MB | Peak / limit |
|---|---|---|---|---|
| stt | 1328 | 878 | 1408 | 94% |
| tts | 272 | 615 | 1024 | 27% |
| gateway | 73 | 74 | 256 | 29% |

Ollama: phi4-mini:3.8b 3.11 GB.
