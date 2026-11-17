# Ollama cold load (M5, D25)

`phi4-mini:3.8b`, 2026-11-16 22:06 UTC, `scripts/measure_ollama_load.sh`.

| Run | Limit MiB | Load s | Peak MiB | File cache MiB | Process MiB |
|---|---|---|---|---|---|
| 1: compose limit, model file not cached | 4480 | 12.7 | 4480 | 1369 | 3092 |
| 2: compose limit, model file cached | 4480 | 21.5 | 4222 | 1009 | 3091 |
| 3: 8 GiB limit, model file cached | 8192 | 22.0 | 3214 | 0 | 3091 |

Ollama is back on the compose limit with the model loaded.
