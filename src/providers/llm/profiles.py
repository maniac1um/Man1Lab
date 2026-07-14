"""Model profile migration, validation, and API key resolution."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from configuration.models import LLMConfig, ModelProfileSpec
from providers.llm.models import ModelProfile, RegistryDiagnostic, RegistryValidationResult

KNOWN_PROVIDERS = frozenset({"openai", "deepseek", "anthropic"})


def resolve_api_key_reference(
    reference: str,
    *,
    environ: dict[str, str] | None = None,
    fallback_config: LLMConfig | None = None,
) -> str:
    env = environ or os.environ
    if not reference:
        return ""
    value = env.get(reference, "").strip()
    if value:
        return value
    if fallback_config is None:
        return ""
    if reference == "OPENAI_API_KEY":
        return fallback_config.openai_api_key.strip()
    if reference == "ANTHROPIC_API_KEY":
        return fallback_config.anthropic_api_key.strip()
    return ""


def build_api_key_resolver(config: LLMConfig) -> Callable[[str], str]:
    def resolver(reference: str) -> str:
        return resolve_api_key_reference(reference, fallback_config=config)

    return resolver


def infer_legacy_provider(config: LLMConfig) -> str:
    base_url = config.openai_base_url.lower()
    model = config.openai_model.lower()
    if "deepseek" in base_url or "deepseek" in model:
        return "deepseek"
    return "openai"


def ensure_profiles(config: LLMConfig) -> LLMConfig:
    """Migrate legacy flat LLM configuration into profile-based layout when needed."""
    if config.profiles:
        return config

    provider = infer_legacy_provider(config)
    default_profile = ModelProfileSpec(
        provider=provider,
        model=config.openai_model or "gpt-4o-mini",
        base_url=config.openai_base_url,
        api_key_reference="OPENAI_API_KEY",
        description="Migrated from legacy LLM configuration.",
    )
    return replace(
        config,
        active=config.active or "default",
        profiles={"default": default_profile},
    )


def profile_from_spec(
    profile_name: str,
    spec: ModelProfileSpec,
    *,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> ModelProfile:
    timestamp = datetime.now(UTC)
    return ModelProfile(
        profile_name=profile_name,
        provider=spec.provider,
        model=spec.model,
        base_url=spec.base_url,
        api_key_reference=spec.api_key_reference,
        organization=spec.organization,
        api_version=spec.api_version,
        temperature=spec.temperature,
        max_tokens=spec.max_tokens,
        enabled=spec.enabled,
        description=spec.description,
        tags=spec.tags,
        created_at=created_at or timestamp,
        updated_at=updated_at or timestamp,
    )


def profile_to_spec(profile: ModelProfile) -> ModelProfileSpec:
    return ModelProfileSpec(
        provider=profile.provider,
        model=profile.model,
        base_url=profile.base_url,
        api_key_reference=profile.api_key_reference,
        organization=profile.organization,
        api_version=profile.api_version,
        temperature=profile.temperature,
        max_tokens=profile.max_tokens,
        enabled=profile.enabled,
        description=profile.description,
        tags=profile.tags,
    )


def validate_profiles(
    profiles: dict[str, ModelProfile],
    *,
    active_profile_name: str,
    known_providers: frozenset[str] = KNOWN_PROVIDERS,
    api_key_resolver: Callable[[str], str] | None = None,
) -> RegistryValidationResult:
    resolver = api_key_resolver or resolve_api_key_reference
    diagnostics: list[RegistryDiagnostic] = []

    if not profiles:
        diagnostics.append(
            RegistryDiagnostic(
                level="error",
                code="profiles.empty",
                message="No model profiles are configured.",
            )
        )
        return RegistryValidationResult(valid=False, diagnostics=tuple(diagnostics))

    if active_profile_name not in profiles:
        diagnostics.append(
            RegistryDiagnostic(
                level="error",
                code="active.missing",
                message=f"Active profile '{active_profile_name}' does not exist.",
                profile_name=active_profile_name,
            )
        )

    seen_names: set[str] = set()
    profile_names: dict[str, str] = {}
    for name, profile in profiles.items():
        if name in seen_names:
            diagnostics.append(
                RegistryDiagnostic(
                    level="error",
                    code="profile.duplicate",
                    message=f"Duplicate profile name '{name}'.",
                    profile_name=name,
                )
            )
        seen_names.add(name)

        existing_key = profile_names.get(profile.profile_name)
        if existing_key is not None and existing_key != name:
            diagnostics.append(
                RegistryDiagnostic(
                    level="error",
                    code="profile.duplicate",
                    message=(
                        f"Duplicate profile_name '{profile.profile_name}' "
                        f"used by '{existing_key}' and '{name}'."
                    ),
                    profile_name=profile.profile_name,
                )
            )
        profile_names[profile.profile_name] = name

        if profile.profile_name != name:
            diagnostics.append(
                RegistryDiagnostic(
                    level="error",
                    code="profile.name_mismatch",
                    message=(
                        f"Profile key '{name}' does not match profile_name "
                        f"'{profile.profile_name}'."
                    ),
                    profile_name=name,
                )
            )

        if not profile.provider:
            diagnostics.append(
                RegistryDiagnostic(
                    level="error",
                    code="profile.missing_provider",
                    message="Profile provider is required.",
                    profile_name=name,
                )
            )
        elif profile.provider not in known_providers:
            diagnostics.append(
                RegistryDiagnostic(
                    level="error",
                    code="profile.unknown_provider",
                    message=f"Unknown provider '{profile.provider}'.",
                    profile_name=name,
                )
            )

        if not profile.model:
            diagnostics.append(
                RegistryDiagnostic(
                    level="error",
                    code="profile.missing_model",
                    message="Profile model is required.",
                    profile_name=name,
                )
            )

        if not profile.api_key_reference:
            diagnostics.append(
                RegistryDiagnostic(
                    level="error",
                    code="profile.missing_api_reference",
                    message="Profile api_key_reference is required.",
                    profile_name=name,
                )
            )

    active_profile = profiles.get(active_profile_name)
    if active_profile is not None:
        if not active_profile.enabled:
            diagnostics.append(
                RegistryDiagnostic(
                    level="error",
                    code="active.disabled",
                    message=f"Active profile '{active_profile_name}' is disabled.",
                    profile_name=active_profile_name,
                )
            )
        elif not resolver(active_profile.api_key_reference):
            diagnostics.append(
                RegistryDiagnostic(
                    level="error",
                    code="active.missing_api_key",
                    message=(
                        f"Active profile '{active_profile_name}' references "
                        f"'{active_profile.api_key_reference}', but no key is available."
                    ),
                    profile_name=active_profile_name,
                )
            )

    valid = not any(item.level == "error" for item in diagnostics)
    return RegistryValidationResult(valid=valid, diagnostics=tuple(diagnostics))
