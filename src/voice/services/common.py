"""What every service shares: health endpoints, error bodies that never echo input, one-at-a-time model work."""

import asyncio
import logging
from collections.abc import Callable
from typing import TypeVar

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

T = TypeVar("T")
log = logging.getLogger("voice")


def error(status: int, code: str, message: str) -> HTTPException:
    """OpenAI-style error body: {"error": {"code", "message"}}. Messages are fixed text, never request content."""
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def configure_logging() -> None:
    """Our INFO lines next to uvicorn's (uvicorn configures only its own loggers)."""
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)


def install_common(app: FastAPI, is_ready: Callable[[], bool]) -> None:
    configure_logging()

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {"status": "ok"}  # liveness: the process answers

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> JSONResponse:
        # readiness: this process can do its job. Dependencies are not checked here (D12).
        ready = is_ready()
        return JSONResponse({"status": "ready" if ready else "loading"}, status_code=200 if ready else 503)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
        return JSONResponse({"error": detail}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default 422 body echoes the submitted values; only field names leave the service.
        fields = sorted({".".join(str(part) for part in e["loc"][1:]) or "body" for e in exc.errors()})
        message = f"invalid or missing: {', '.join(fields)}"
        return JSONResponse({"error": {"code": "invalid_request", "message": message}}, status_code=400)


class Worker:
    """Runs blocking model calls one at a time, off the event loop, with a bounded queue.

    One model instance uses all the CPU threads it was given, so two calls at once only slow each other down.
    Requests beyond `max_waiting` get 503 at once instead of piling up; more capacity is more replicas (D11).
    """

    def __init__(self, max_waiting: int) -> None:
        self.max_waiting = max_waiting
        self.waiting = 0
        self._lock = asyncio.Lock()

    async def run(self, func: Callable[..., T], *args) -> T:
        if self._lock.locked() and self.waiting >= self.max_waiting:
            raise error(503, "busy", "too many requests waiting; retry later")
        self.waiting += 1
        try:
            await self._lock.acquire()  # a client that disconnects while waiting cancels here
        finally:
            self.waiting -= 1
        try:
            return await run_in_threadpool(func, *args)
        finally:
            self._lock.release()
