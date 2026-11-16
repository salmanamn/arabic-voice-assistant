# Images built in M4

- Date: 2026-11-16 18:43 UTC; Docker Engine 29.9.2; `scripts/check_images.py`: all checks passed
- Base images (Dockerfile):
  - `python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90`
  - `ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85`

| Image | Image id | Size MB (as Docker reports it) | Of which /app/.venv MB | Python packages | User |
|---|---|---|---|---|---|
| `voice-stt:local` | `sha256:c241357643787aa933da461c2600e43b7379f8ef49ac093f42294c3b1ee1eba1` | 816 | 469 | 34 | 10001:10001 |
| `voice-tts:local` | `sha256:46d3b498e56a5d4525934814b97b7a2094043c4449346886a0b9fb54e1ae57f8` | 501 | 215 | 22 | 10001:10001 |
| `voice-gateway:local` | `sha256:df4cca9237743bdc950b23aa99ba35380433d515da35b5c8028fd467a048c99c` | 246 | 37 | 22 | 10001:10001 |
| `voice-models:local` | `sha256:6ad13140e93c414c2c56c83e2c36a0c24f95e2ffbd2359c5776d3d7e0ef00b0e` | 228 | 32 | 16 | 10001:10001 |

The image id is local: nothing was pushed in M4. The id is the digest a registry will show only when the engine uses the containerd image store and the image is pushed as it is.
