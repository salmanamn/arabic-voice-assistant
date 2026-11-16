# One Dockerfile, four images (D19): `stt`, `tts`, `gateway` and the model-fetch job `models`.
# Build one with `docker build --target stt .`, or all four with `docker compose build`.
#
# Base images are pinned by digest; scripts/pin_images.py resolves and rewrites the two lines below.
ARG PYTHON_IMAGE=python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85

FROM ${UV_IMAGE} AS uv

# ---- build: one virtual environment per image, each from its own dependency group (D9) ----------------------
FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
# copy mode: the environment must not link into the build cache; bytecode is compiled now because the
# containers run on a read-only filesystem; never download another Python than the image's.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
COPY pyproject.toml uv.lock ./

# Each environment in two steps: third-party packages first (this layer is rebuilt only when uv.lock changes),
# then the project itself as a normal installed package (--no-editable: the source tree is not in the image).
FROM build AS venv-stt
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-default-groups --group stt --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-default-groups --group stt --no-editable

FROM build AS venv-tts
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-default-groups --group tts --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-default-groups --group tts --no-editable

FROM build AS venv-gateway
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-default-groups --group gateway --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-default-groups --group gateway --no-editable

FROM build AS venv-models
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-default-groups --group models --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-default-groups --group models --no-editable

# ---- runtime: what all four images share ---------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime
# No installer in a running service. /models is the mount point of the models volume; a new named volume takes
# its owner from this directory, so the fetch job (uid 10001) can write to it.
# zlib1g: Debian security fix not yet in the base image (D22); remove once the base digest carries it.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends --only-upgrade "zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1" \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall --yes --quiet --root-user-action=ignore pip \
    && install -d -o 10001 -g 10001 /models
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    MODELS_DIR=/models
WORKDIR /app
# A number, not a name: Kubernetes can check runAsNonRoot only against a numeric user.
USER 10001:10001
LABEL org.opencontainers.image.source="https://github.com/salmanamn/arabic-voice-assistant"

# ---- speech to text ------------------------------------------------------------------------------------------
FROM runtime AS stt
COPY --from=venv-stt /app/.venv /app/.venv
# faster-whisper ships the hub client; this service never downloads (the model comes from the volume, D20).
ENV HF_HUB_OFFLINE=1
EXPOSE 8000
LABEL org.opencontainers.image.title="voice-stt" \
    org.opencontainers.image.description="Speech to text: OpenAI transcription route served by faster-whisper"
CMD ["uvicorn", "--factory", "voice.services.stt_app:create_app", "--host", "0.0.0.0", "--port", "8000"]

# ---- text to speech: the only image with Piper (GPL-3.0-or-later, D3) ----------------------------------------
FROM runtime AS tts
COPY --from=venv-tts /app/.venv /app/.venv
EXPOSE 8000
LABEL org.opencontainers.image.title="voice-tts" \
    org.opencontainers.image.description="Text to speech: OpenAI speech route served by Piper" \
    org.opencontainers.image.licenses="GPL-3.0-or-later"
CMD ["uvicorn", "--factory", "voice.services.tts_app:create_app", "--host", "0.0.0.0", "--port", "8000"]

# ---- gateway -------------------------------------------------------------------------------------------------
FROM runtime AS gateway
COPY --from=venv-gateway /app/.venv /app/.venv
EXPOSE 8080
LABEL org.opencontainers.image.title="voice-gateway" \
    org.opencontainers.image.description="Gateway: one assistant turn over HTTP and the push-to-talk page"
CMD ["uvicorn", "--factory", "voice.services.gateway_app:create_app", "--host", "0.0.0.0", "--port", "8080"]

# ---- model-fetch job: the lock travels inside the image, the models never do (D4, D20) -----------------------
FROM runtime AS models
COPY --from=venv-models /app/.venv /app/.venv
COPY models.lock.json /app/models.lock.json
ENV MODELS_LOCK=/app/models.lock.json
LABEL org.opencontainers.image.title="voice-models" \
    org.opencontainers.image.description="Job: download the locked model files into a volume and verify them"
ENTRYPOINT ["python", "-m", "voice.fetch_job"]
CMD ["stt-small", "tts-ar-kareem-medium"]