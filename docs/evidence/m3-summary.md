# M3 summary: Arabic quality and the model choice

## Speech to text

| Model | Set | n | CER | WER | p50 s | p90 s | RTF | Threads |
|---|---|---|---|---|---|---|---|---|
| `stt-small` | own | 20 | 10.1% | 20.9% | 1.75 | 1.96 | 0.25 | 6 |
| `stt-small` | fleurs | 40 | 7.6% | 23.7% | 2.71 | 3.23 | 0.24 | 6 |
| `stt-turbo` | own | 20 | 7.2% | 13.9% | 8.01 | 8.99 | 1.19 | 6 |
| `stt-turbo` | fleurs | 40 | 3.9% | 11.0% | 10.30 | 12.17 | 0.94 | 6 |

By style:

- `stt-small` own/gulf: n=6, CER 9.6%, WER 27.6%
- `stt-small` own/msa: n=14, CER 10.2%, WER 18.6%
- `stt-small` fleurs/fleurs-female: n=40, CER 7.6%, WER 23.7%
- `stt-turbo` own/gulf: n=6, CER 10.4%, WER 34.5%
- `stt-turbo` own/msa: n=14, CER 6.2%, WER 7.0%
- `stt-turbo` fleurs/fleurs-female: n=40, CER 3.9%, WER 11.0%

**Choice: `stt-small`** — own-set CER 10.1% at p90 1.96 s, within the 2.5 s budget; over budget: stt-turbo p90 8.99 s.

## Chat model

| Model | Correct | Arabic | Errors | p50 s | p90 s | tok/s | Memory GB |
|---|---|---|---|---|---|---|---|
| `phi4-mini:3.8b` | 54% | 96% | 0 | 1.47 | 2.38 | 6.9 | 3.1 |
| `gemma3:4b` | 79% | 100% | 0 | 4.73 | 5.34 | 4.0 | 2.9 |
| `qwen3.5:4b@none` | 75% | 100% | 0 | 5.91 | 8.31 | 3.0 | 3.1 |
| `command-r7b-arabic:7b` | 83% | 100% | 0 | 30.57 | 33.12 | 0.5 | 5.6 |

**Choice: `phi4-mini:3.8b`** — 54% correct, 96% Arabic, p90 2.38 s, 3.1 GB; below the 80% correctness bar: a lab stand-in until Azure OpenAI (M8); ruled out: command-r7b-arabic:7b (p90 33.12 s), gemma3:4b (p90 5.34 s), qwen3.5:4b@none (p90 8.31 s).

## Time budget (end of question to answer audio, warm, laptop)

Measured 2026-11-16 15:48 UTC: 20/20 turns of the `own` set, `stt-small` (6 threads) + `phi4-mini:3.8b`.

| Stage | Budget p90 s | Measured p50 s | Measured p90 s | |
|---|---|---|---|---|
| stt | 2.5 | 2.06 | 2.33 | OK |
| chat | 3.5 | 1.72 | 3.61 | OVER |
| tts | 0.8 | 0.26 | 0.74 | OK |
| other | 0.2 | 0.00 | 0.00 | OK |
| total | 7 | 4.49 | 6.84 | OK |

Peak memory: stt 878 MB, tts 615 MB, gateway 74 MB; Ollama: phi4-mini:3.8b 3.11 GB.

**Budget: p50 4.49 s / p90 6.84 s against 7 s; over: chat p90 3.61 s > 3.5 s.**

Rules: `voice.quality.choose_stt` / `choose_chat`, budget `voice.quality.Budget` (decisions D16–D18).
