"""A stand-in for Ollama's OpenAI-compatible chat endpoint, for the cluster test in CI (`ollama.fake=true`, D34).

Answers every chat request with one fixed Arabic sentence, so a turn through the cluster can be checked without a
2.5 GB model. Serves the routes the chart and the gateway use: /api/version (probes), /api/ps (shows the model as
loaded), /v1/chat/completions. Standard library only: it runs in the gateway image, which has Python."""

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = os.environ["CHAT_MODEL"]
ANSWER = "عاصمة مملكة البحرين هي المنامة."


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, body: object) -> None:
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/api/version":
            return self.send_json(200, {"version": "fake"})
        if self.path == "/api/ps":
            return self.send_json(200, {"models": [{"name": MODEL, "model": MODEL, "size": 0}]})
        self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if self.path != "/v1/chat/completions":
            return self.send_json(404, {"error": "not found"})
        if request.get("model") != MODEL:
            return self.send_json(404, {"error": {"message": f"model {request.get('model')!r} not found"}})
        self.send_json(
            200,
            {
                "id": "fake",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": MODEL,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": ANSWER}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    def log_message(self, *args) -> None:  # requests are not logged (the gateway logs lengths and times)
        pass


ThreadingHTTPServer(("0.0.0.0", 11434), Handler).serve_forever()  # noqa: S104 (the pod's own port)
