from anthropic import Anthropic

import config
from llm.provider import LLMMessage, LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key if api_key is not None else config.ANTHROPIC_API_KEY
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self._client = Anthropic(api_key=key)
        self._model = model or config.ANTHROPIC_MODEL

    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        system_prompt = ""
        chat_messages: list[dict[str, str]] = []
        for message in messages:
            if message.role == "system":
                system_prompt = message.content
            else:
                chat_messages.append({"role": message.role, "content": message.content})

        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            temperature=temperature,
            system=system_prompt,
            messages=chat_messages,
        )
        text_blocks = [block.text for block in response.content if block.type == "text"]
        if not text_blocks:
            raise RuntimeError("Anthropic returned an empty response")
        return "\n".join(text_blocks)
