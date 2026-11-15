"""The assistant's answer: one chat completion on any OpenAI-compatible endpoint.

Locally that is Ollama's /v1 API (the key is ignored). On Azure it will be Azure OpenAI's v1 endpoint with an
Entra ID token as the key; reasoning models there take `reasoning_effort` and `max_completion_tokens` and reject
`temperature` and `max_tokens`, which is what `reasoning_effort` switches (same split as ticket-triage-agent D19).
"""

import time
from dataclasses import dataclass

from openai import OpenAI

from voice.settings import Settings

# "You are a voice assistant. Answer only in Modern Standard Arabic, in one or two short sentences. Your answer
# will be read aloud: no lists, symbols, formatting or non-Arabic words. If the question is unclear, ask the user
# to repeat it."
SYSTEM_PROMPT = (
    "أنت مساعد صوتي. أجب باللغة العربية الفصحى فقط، في جملة أو جملتين قصيرتين. "
    "إجابتك ستقرأ بصوت مسموع: لا تستخدم قوائم ولا رموزا ولا تنسيقا ولا كلمات بغير العربية. "
    "إذا لم يكن السؤال واضحا فاطلب من المستخدم أن يعيده."
)
TEMPERATURE = 0.2


@dataclass(frozen=True)
class Reply:
    text: str
    seconds: float
    completion_tokens: int | None


class Assistant:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        max_tokens: int = 160,
        reasoning_effort: str = "",
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)

    @classmethod
    def from_settings(cls, settings: Settings) -> "Assistant":
        return cls(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.chat_model,
            max_tokens=settings.chat_max_tokens,
            reasoning_effort=settings.chat_reasoning_effort,
        )

    def reply(self, question: str) -> Reply:
        if self.reasoning_effort:
            shape = {"reasoning_effort": self.reasoning_effort, "max_completion_tokens": self.max_tokens}
        else:
            shape = {"temperature": TEMPERATURE, "max_tokens": self.max_tokens}
        started = time.perf_counter()
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}],
            **shape,
        )
        text = (completion.choices[0].message.content or "").strip()
        tokens = completion.usage.completion_tokens if completion.usage else None
        return Reply(text=text, seconds=time.perf_counter() - started, completion_tokens=tokens)
