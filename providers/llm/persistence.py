"""Persist model registry state to user configuration overlays."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from omegaconf import OmegaConf

from configuration.models import LLMConfig, ModelProfileSpec
from configuration.paths import resolve_llm_user_profiles_path
from providers.llm.models import ModelProfile, RegistryValidationResult
from providers.llm.profiles import profile_to_spec
from providers.llm.registry import ModelRegistry


@dataclass(frozen=True)
class ModelImportReport:
    successful: bool
    message: str
    added: tuple[str, ...] = ()
    replaced: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    validation: RegistryValidationResult | None = None


def resolve_persistence_path(path: Path | None = None) -> Path:
    return path or resolve_llm_user_profiles_path()


def load_persisted_llm_config(path: Path | None = None) -> LLMConfig | None:
    target = resolve_persistence_path(path)
    if not target.exists():
        return None

    container = OmegaConf.to_container(OmegaConf.load(target), resolve=True)
    if not isinstance(container, dict):
        return None

    profiles_raw = container.get("profiles") or {}
    profiles: dict[str, ModelProfileSpec] = {}
    if isinstance(profiles_raw, dict):
        for name, profile in profiles_raw.items():
            if not isinstance(profile, dict):
                continue
            tags_raw = profile.get("tags") or []
            temperature = profile.get("temperature")
            max_tokens = profile.get("max_tokens")
            profiles[str(name)] = ModelProfileSpec(
                provider=str(profile.get("provider", "")),
                model=str(profile.get("model", "")),
                base_url=str(profile.get("base_url", "") or ""),
                api_key_reference=str(
                    profile.get("api_key_reference", "OPENAI_API_KEY") or "OPENAI_API_KEY"
                ),
                organization=str(profile.get("organization", "") or ""),
                api_version=str(profile.get("api_version", "") or ""),
                temperature=float(temperature) if temperature is not None else None,
                max_tokens=int(max_tokens) if max_tokens is not None else None,
                enabled=bool(profile.get("enabled", True)),
                description=str(profile.get("description", "") or ""),
                tags=tuple(str(tag) for tag in tags_raw),
            )

    return LLMConfig(
        active=str(container.get("active", "default") or "default"),
        profiles=profiles or None,
    )


def merge_llm_config(base: LLMConfig, overlay: LLMConfig | None) -> LLMConfig:
    if overlay is None:
        return base
    from dataclasses import replace

    merged_profiles = dict(base.profiles or {})
    if overlay.profiles:
        merged_profiles.update(overlay.profiles)
    return replace(
        base,
        active=overlay.active or base.active,
        profiles=merged_profiles or None,
    )


def registry_to_llm_config(
    profiles: dict[str, ModelProfile],
    *,
    active: str,
    base_config: LLMConfig,
) -> LLMConfig:
    from dataclasses import replace

    specs = {name: profile_to_spec(profile) for name, profile in profiles.items()}
    return replace(base_config, active=active, profiles=specs)


def save_registry_state(
    profiles: dict[str, ModelProfile],
    *,
    active: str,
    base_config: LLMConfig,
    path: Path | None = None,
) -> Path:
    target = resolve_persistence_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    llm_config = registry_to_llm_config(profiles, active=active, base_config=base_config)

    payload: dict[str, object] = {"active": llm_config.active, "profiles": {}}
    for name, spec in (llm_config.profiles or {}).items():
        profile_payload: dict[str, object] = {
            "provider": spec.provider,
            "model": spec.model,
            "api_key_reference": spec.api_key_reference,
            "enabled": spec.enabled,
        }
        if spec.base_url:
            profile_payload["base_url"] = spec.base_url
        if spec.organization:
            profile_payload["organization"] = spec.organization
        if spec.api_version:
            profile_payload["api_version"] = spec.api_version
        if spec.temperature is not None:
            profile_payload["temperature"] = spec.temperature
        if spec.max_tokens is not None:
            profile_payload["max_tokens"] = spec.max_tokens
        if spec.description:
            profile_payload["description"] = spec.description
        if spec.tags:
            profile_payload["tags"] = list(spec.tags)
        payload["profiles"][name] = profile_payload

    OmegaConf.save(OmegaConf.create(payload), target)
    return target


def export_portable_config(
    profiles: dict[str, ModelProfile],
    *,
    active: str,
    base_config: LLMConfig,
    path: Path,
) -> Path:
    return save_registry_state(
        profiles,
        active=active,
        base_config=base_config,
        path=path,
    )


def import_portable_config(
    registry: ModelRegistry,
    path: Path,
    *,
    replace: bool = False,
    skip_existing: bool = False,
) -> ModelImportReport:
    loaded = load_persisted_llm_config(path)
    if loaded is None or not loaded.profiles:
        return ModelImportReport(
            successful=False,
            message=f"No portable profiles found in {path}.",
        )

    added: list[str] = []
    replaced: list[str] = []
    skipped: list[str] = []

    for name, spec in loaded.profiles.items():
        existing = registry.get_profile(name)
        if existing is not None:
            if skip_existing:
                skipped.append(name)
                continue
            if not replace:
                return ModelImportReport(
                    successful=False,
                    message=f"Duplicate profile '{name}' detected.",
                )
            replaced.append(name)
        else:
            added.append(name)
        registry.register_profile(name, spec)

    if loaded.active:
        registry.set_active_profile(loaded.active)

    validation = registry.validate()
    if not validation.valid:
        return ModelImportReport(
            successful=False,
            message="Imported profiles failed validation.",
            added=tuple(added),
            replaced=tuple(replaced),
            skipped=tuple(skipped),
            validation=validation,
        )

    return ModelImportReport(
        successful=True,
        message=f"Imported {len(added) + len(replaced)} profile(s) from {path}.",
        added=tuple(added),
        replaced=tuple(replaced),
        skipped=tuple(skipped),
        validation=validation,
    )
