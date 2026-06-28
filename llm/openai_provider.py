from openai import OpenAI

import config
from llm.provider import LLMMessage, LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key if api_key is not None else config.OPENAI_API_KEY
        if not key:
            raise ValueError("OPENAI_API_KEY is not set")
        self._client = OpenAI(api_key=key)
        self._model = model or config.OPENAI_MODEL

    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            messages=[{"role": message.role, "content": message.content} for message in messages],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned an empty response")
        return content
