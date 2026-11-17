# One turn through the services (compose containers)

- Date: 2026-11-16 22:16 UTC; 20/20 turns of the `own` set after one warm-up turn
- Models: `stt-small` (6 threads) + `phi4-mini:3.8b`
- Compared with `out/m3/turns.json`: 2026-11-16 15:48 UTC, `stt-small` (6 threads) + `phi4-mini:3.8b`

| Stage | Budget p90 s | Before p50 s | Before p90 s | Now p50 s | Now p90 s | p90 change s | |
|---|---|---|---|---|---|---|---|
| stt | 2.5 | 2.06 | 2.33 | 2.30 | 7.38 | +5.05 | OVER |
| chat | 3.5 | 1.72 | 3.61 | 2.13 | 5.18 | +1.57 | OVER |
| tts | 0.8 | 0.26 | 0.74 | 0.34 | 1.04 | +0.30 | OVER |
| other | 0.2 | 0.00 | 0.00 | 0.00 | 0.00 | +0.00 | OK |
| total | 7 | 4.49 | 6.84 | 5.53 | 14.08 | +7.24 | OVER |

| Service | Peak memory MB | Before MB | Limit MB | Peak / limit |
|---|---|---|---|---|
| stt | 883 | 878 | 2048 | 43% |
| tts | 574 | 615 | 1024 | 56% |
| gateway | 78 | 74 | 256 | 30% |

Ollama: phi4-mini:3.8b 3.11 GB.
