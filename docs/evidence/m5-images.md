# Images built in M4

- Date: 2026-11-16 22:44 UTC; Docker Engine 29.9.2; `scripts/check_images.py`: all checks passed
- Base images (Dockerfile):
  - `python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90`
  - `ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85`

| Image | Image id | Size MB (as Docker reports it) | Of which /app/.venv MB | Python packages | User |
|---|---|---|---|---|---|
| `voice-stt:local` | `sha256:7f0a81938f0d6f4cefb74f3e10f0af53b63e131a66e79601261458cb1a846f77` | 816 | 469 | 34 | 10001:10001 |
| `voice-tts:local` | `sha256:96a67adb0c0d532859110c0a7fe509e6e28bf98abbc5b10ac87264da432c1bb2` | 501 | 215 | 22 | 10001:10001 |
| `voice-gateway:local` | `sha256:05021259b361b6e5f72dd5a8fa7eb8e508c4722b71edc4ebf769ac17c445743a` | 246 | 37 | 22 | 10001:10001 |
| `voice-models:local` | `sha256:f347c3c5b5758f23c9894fa336e87108fdb5737456dfc3d0fa5b2aa3228e596f` | 228 | 32 | 16 | 10001:10001 |

The image id is local: nothing was pushed in M4. The id is the digest a registry will show only when the engine uses the containerd image store and the image is pushed as it is.
