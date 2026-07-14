"""Adapters between the LLM manager and the legacy business port."""

from __future__ import annotations

from providers.llm.base import LLMProvider as InfrastructureLLMProvider
from providers.llm.manager import LLMManager
from providers.llm.models import LLMMessage as InfrastructureLLMMessage
from llm.provider import LLMMessage, LLMProvider


def to_infrastructure_messages(messages: list[LLMMessage]) -> list[InfrastructureLLMMessage]:
    return [
        InfrastructureLLMMessage(role=message.role, content=message.content) for message in messages
    ]


class LLMManagerCompleteAdapter(LLMProvider):
    """Expose LLMManager through the legacy complete() business port."""

    def __init__(self, manager: LLMManager) -> None:
        self._manager = manager

    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        return self._manager.generate(to_infrastructure_messages(messages), temperature=temperature)


class ProviderCompleteAdapter(LLMProvider):
    """Expose an infrastructure provider through the legacy complete() business port."""

    def __init__(self, provider: InfrastructureLLMProvider) -> None:
        self._provider = provider

    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        return self._provider.generate(to_infrastructure_messages(messages), temperature=temperature)
