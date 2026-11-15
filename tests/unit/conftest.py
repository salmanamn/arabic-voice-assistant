"""Shared test helpers: run an ASGI app on a real local port (the openai SDK needs a real HTTP server)."""

import threading
import time

import pytest
import uvicorn


class Running:
    def __init__(self, app) -> None:
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="on")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            if time.monotonic() > deadline or not self.thread.is_alive():
                raise RuntimeError("test server did not start")
            time.sleep(0.01)
        port = self.server.servers[0].sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    def __exit__(self, *exc) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)


@pytest.fixture
def serve():
    """serve(app) -> base URL; every server is stopped at the end of the test."""
    running: list[Running] = []

    def start(app) -> str:
        server = Running(app)
        url = server.__enter__()
        running.append(server)
        return url

    yield start
    for server in running:
        server.__exit__()
