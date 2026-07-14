"""Canonical model profile and registry result types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LLMMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class LLMHealthStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    status: str
    model: str = ""
    message: str = ""


@dataclass(frozen=True)
class ModelProfile:
    profile_name: str
    provider: str
    model: str
    base_url: str = ""
    api_key_reference: str = "OPENAI_API_KEY"
    organization: str = ""
    api_version: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    enabled: bool = True
    description: str = ""
    tags: tuple[str, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class RegistryDiagnostic:
    level: str
    code: str
    message: str
    profile_name: str = ""


@dataclass(frozen=True)
class RegistryValidationResult:
    valid: bool
    diagnostics: tuple[RegistryDiagnostic, ...] = ()

    @property
    def errors(self) -> tuple[RegistryDiagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.level == "error")

    @property
    def warnings(self) -> tuple[RegistryDiagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.level == "warning")
