"""The chat request that leaves the process, checked against a local OpenAI-compatible stand-in."""

import json
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from voice.llm import ENTRA_SCOPE, SYSTEM_PROMPT, Assistant
from voice.settings import load
from voice.textnorm import arabic_ratio


class FakeChat(BaseHTTPRequestHandler):
    requests: ClassVar[list[dict]] = []
    answer = "عاصمة مملكة البحرين هي المنامة."

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        payload = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": body["model"],
            "choices": [
                {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": self.answer}}
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 9, "total_tokens": 59},
        }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def endpoint():
    FakeChat.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeChat)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()
    server.server_close()


def test_classic_model_request_and_reply(endpoint):
    assistant = Assistant(base_url=endpoint, api_key="ollama", model="phi4-mini:3.8b", max_tokens=160)

    reply = assistant.reply("ما هي عاصمة مملكة البحرين؟")

    assert reply.text == "عاصمة مملكة البحرين هي المنامة."
    assert reply.completion_tokens == 9
    assert reply.seconds > 0
    (request,) = FakeChat.requests
    assert request["path"] == "/v1/chat/completions"
    assert request["auth"] == "Bearer ollama"
    assert request["body"]["model"] == "phi4-mini:3.8b"
    assert request["body"]["messages"] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "ما هي عاصمة مملكة البحرين؟"},
    ]
    assert request["body"]["temperature"] == 0.2
    assert request["body"]["max_tokens"] == 160
    assert "reasoning_effort" not in request["body"]


def test_reasoning_model_gets_no_temperature_and_no_max_tokens(endpoint):
    assistant = Assistant(base_url=endpoint, api_key="k", model="gpt-5.4-mini", max_tokens=400, reasoning_effort="low")

    assistant.reply("سؤال")

    body = FakeChat.requests[0]["body"]
    assert body["reasoning_effort"] == "low"
    assert body["max_completion_tokens"] == 400
    assert "temperature" not in body
    assert "max_tokens" not in body


def test_thinking_off_keeps_the_classic_shape(endpoint):
    assistant = Assistant(base_url=endpoint, api_key="k", model="qwen3.5:4b", max_tokens=160, reasoning_effort="none")

    assistant.reply("سؤال")

    body = FakeChat.requests[0]["body"]
    assert body["reasoning_effort"] == "none"
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 160
    assert "max_completion_tokens" not in body


def test_empty_content_becomes_an_empty_reply(endpoint, monkeypatch):
    monkeypatch.setattr(FakeChat, "answer", None)
    assistant = Assistant(base_url=endpoint, api_key="k", model="m")
    assert assistant.reply("سؤال").text == ""


def test_system_prompt_is_arabic_and_asks_for_short_spoken_answers():
    assert arabic_ratio(SYSTEM_PROMPT) == 1.0
    assert "العربية الفصحى" in SYSTEM_PROMPT
    assert "جملة أو جملتين" in SYSTEM_PROMPT


@pytest.fixture
def fake_identity(monkeypatch):
    """azure.identity as the gateway image has it, without a network: every token request is recorded."""
    calls: list[str] = []
    module = types.ModuleType("azure.identity")

    class DefaultAzureCredential:
        pass

    def get_bearer_token_provider(credential, scope):
        assert isinstance(credential, DefaultAzureCredential)

        def token() -> str:
            calls.append(scope)
            return "entra-token"

        return token

    module.DefaultAzureCredential = DefaultAzureCredential
    module.get_bearer_token_provider = get_bearer_token_provider
    monkeypatch.setitem(sys.modules, "azure.identity", module)
    return calls


def test_entra_auth_sends_a_token_and_never_the_key(endpoint, fake_identity):
    settings = load({"OPENAI_BASE_URL": endpoint, "OPENAI_AUTH": "entra", "OPENAI_API_KEY": "must-not-be-sent"})

    Assistant.from_settings(settings).reply("سؤال")

    assert FakeChat.requests[0]["auth"] == "Bearer entra-token"
    assert fake_identity == [ENTRA_SCOPE]  # Azure OpenAI's scope, asked for at request time


def test_key_auth_is_the_default_and_needs_no_azure_identity(endpoint, monkeypatch):
    monkeypatch.setitem(sys.modules, "azure.identity", None)  # importing it would fail: the laptop path never does
    Assistant.from_settings(load({"OPENAI_BASE_URL": endpoint})).reply("سؤال")
    assert FakeChat.requests[0]["auth"] == "Bearer ollama"
