"""Model management reports and operations for the LLM manager."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from configuration.models import LLMConfig, ModelProfileSpec
from providers.llm.models import ModelProfile, RegistryValidationResult
from providers.llm.persistence import save_registry_state
from providers.llm.profiles import profile_from_spec
from providers.llm.provider_registry import ProviderRegistry
from providers.llm.registry import ModelRegistry


@dataclass(frozen=True)
class ModelProfileSummary:
    profile_name: str
    provider: str
    model: str
    enabled: bool
    active: bool
    description: str = ""


@dataclass(frozen=True)
class ModelListReport:
    profiles: list[ModelProfileSummary] = field(default_factory=list)


@dataclass(frozen=True)
class CurrentModelReport:
    profile_name: str
    provider: str
    model: str
    base_url: str
    api_key_reference: str
    enabled: bool


@dataclass(frozen=True)
class ModelChangeReport:
    successful: bool
    message: str
    active_profile: str = ""
    validation: RegistryValidationResult | None = None


@dataclass(frozen=True)
class ModelTestReport:
    profile_name: str
    provider: str
    model: str
    authentication: str
    connection: str
    latency_ms: float | None
    result: str
    message: str


def build_model_list_report(registry: ModelRegistry) -> ModelListReport:
    active_name = registry.active_profile_name
    summaries = [
        ModelProfileSummary(
            profile_name=profile.profile_name,
            provider=profile.provider,
            model=profile.model,
            enabled=profile.enabled,
            active=profile.profile_name == active_name,
            description=profile.description,
        )
        for profile in registry.list_profiles()
    ]
    return ModelListReport(profiles=summaries)


def build_current_model_report(registry: ModelRegistry) -> CurrentModelReport | None:
    profile = registry.get_active_profile()
    if profile is None:
        return None
    return CurrentModelReport(
        profile_name=profile.profile_name,
        provider=profile.provider,
        model=profile.model,
        base_url=profile.base_url,
        api_key_reference=profile.api_key_reference,
        enabled=profile.enabled,
    )


def test_model_profile(
    registry: ModelRegistry,
    provider_registry: ProviderRegistry,
    *,
    profile_name: str | None = None,
) -> ModelTestReport:
    target_name = profile_name or registry.active_profile_name
    profile = registry.get_profile(target_name)
    if profile is None:
        return ModelTestReport(
            profile_name=target_name,
            provider="",
            model="",
            authentication="error",
            connection="skipped",
            latency_ms=None,
            result="failed",
            message=f"Profile '{target_name}' was not found.",
        )

    api_key = registry.resolve_api_key(profile)
    authentication = "ok" if api_key else "error"
    if not api_key:
        return ModelTestReport(
            profile_name=profile.profile_name,
            provider=profile.provider,
            model=profile.model,
            authentication=authentication,
            connection="skipped",
            latency_ms=None,
            result="failed",
            message=f"API key reference '{profile.api_key_reference}' is not configured.",
        )

    provider_config = registry.build_provider_config(profile, api_key)
    try:
        provider = provider_registry.resolve(profile.provider, provider_config)
    except (KeyError, ValueError) as exc:
        return ModelTestReport(
            profile_name=profile.profile_name,
            provider=profile.provider,
            model=profile.model,
            authentication=authentication,
            connection="error",
            latency_ms=None,
            result="failed",
            message=str(exc),
        )

    started = time.perf_counter()
    try:
        health = provider.health_check()
    except Exception as exc:
        return ModelTestReport(
            profile_name=profile.profile_name,
            provider=profile.provider,
            model=profile.model,
            authentication=authentication,
            connection="error",
            latency_ms=None,
            result="failed",
            message=str(exc),
        )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    connection = "ok" if health.status == "ok" else "error"
    result = "passed" if health.status == "ok" else "failed"
    return ModelTestReport(
        profile_name=profile.profile_name,
        provider=health.provider,
        model=health.model or profile.model,
        authentication=authentication,
        connection=connection,
        latency_ms=latency_ms,
        result=result,
        message=health.message,
    )


def persist_registry(
    registry: ModelRegistry,
    base_config: LLMConfig,
    *,
    path: Path | None = None,
) -> Path:
    return save_registry_state(
        registry.export_profiles(),
        active=registry.active_profile_name,
        base_config=base_config,
        path=path,
    )


def add_model_profile(
    registry: ModelRegistry,
    *,
    profile_name: str,
    provider: str,
    model: str,
    base_url: str = "",
    api_key_reference: str = "OPENAI_API_KEY",
    temperature: float | None = None,
    max_tokens: int | None = None,
    description: str = "",
    enabled: bool = True,
) -> RegistryValidationResult:
    spec = ModelProfileSpec(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key_reference=api_key_reference,
        temperature=temperature,
        max_tokens=max_tokens,
        description=description,
        enabled=enabled,
    )
    profile = profile_from_spec(profile_name, spec)
    return registry.add_profile(profile)
