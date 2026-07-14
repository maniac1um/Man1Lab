from abc import ABC, abstractmethod

from providers.llm.models import LLMMessage

__all__ = ["LLMMessage", "LLMProvider"]


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        """Return the model completion for the given messages."""
