# One turn through the services (compose containers)

- Date: 2026-11-16 19:42 UTC; 20/20 turns of the `own` set after one warm-up turn
- Models: `stt-small` (6 threads) + `phi4-mini:3.8b`
- Compared with `out/m3/turns.json`: 2026-11-16 15:48 UTC, `stt-small` (6 threads) + `phi4-mini:3.8b`

| Stage | Budget p90 s | Before p50 s | Before p90 s | Now p50 s | Now p90 s | p90 change s | |
|---|---|---|---|---|---|---|---|
| stt | 2.5 | 2.06 | 2.33 | 2.55 | 8.36 | +6.03 | OVER |
| chat | 3.5 | 1.72 | 3.61 | 2.13 | 4.57 | +0.96 | OVER |
| tts | 0.8 | 0.26 | 0.74 | 0.34 | 0.93 | +0.19 | OVER |
| other | 0.2 | 0.00 | 0.00 | 0.00 | 0.00 | +0.00 | OK |
| total | 7 | 4.49 | 6.84 | 5.45 | 11.96 | +5.12 | OVER |

| Service | Peak memory MB | Before MB | Limit MB | Peak / limit |
|---|---|---|---|---|
| stt | 880 | 878 | 2048 | 43% |
| tts | 492 | 615 | 1024 | 48% |
| gateway | 70 | 74 | 256 | 27% |

Ollama: phi4-mini:3.8b 3.11 GB.
