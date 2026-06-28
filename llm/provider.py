from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LLMMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        """Return the model completion for the given messages."""
