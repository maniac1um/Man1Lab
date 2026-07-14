"""Model registry — profile lifecycle and active profile resolution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from configuration.models import LLMConfig, ModelProfileSpec
from providers.llm.models import ModelProfile, RegistryValidationResult
from providers.llm.profiles import (
    build_api_key_resolver,
    ensure_profiles,
    profile_from_spec,
    validate_profiles,
)


class ModelRegistry:
    """Own configured model profile lifecycle without calling providers."""

    def __init__(
        self,
        config: LLMConfig,
        *,
        api_key_resolver: Callable[[str], str] | None = None,
    ) -> None:
        self._source_config = ensure_profiles(config)
        self._api_key_resolver = api_key_resolver or build_api_key_resolver(self._source_config)
        self._active_profile_name = self._source_config.active or "default"
        self._profiles = self._load_profiles(self._source_config.profiles or {})
        self._last_validation = self.validate()

    @property
    def active_profile_name(self) -> str:
        return self._active_profile_name

    @property
    def last_validation(self) -> RegistryValidationResult:
        return self._last_validation

    def list_profiles(self) -> list[ModelProfile]:
        return [self._profiles[name] for name in sorted(self._profiles)]

    def get_profile(self, profile_name: str) -> ModelProfile | None:
        return self._profiles.get(profile_name)

    def get_active_profile(self) -> ModelProfile | None:
        return self._profiles.get(self._active_profile_name)

    def set_active_profile(self, profile_name: str) -> RegistryValidationResult:
        if profile_name not in self._profiles:
            self._last_validation = validate_profiles(
                self._profiles,
                active_profile_name=profile_name,
                api_key_resolver=self._api_key_resolver,
            )
            return self._last_validation
        self._active_profile_name = profile_name
        self._last_validation = self.validate()
        return self._last_validation

    def add_profile(self, profile: ModelProfile) -> RegistryValidationResult:
        self._profiles[profile.profile_name] = profile
        self._last_validation = self.validate()
        return self._last_validation

    def remove_profile(self, profile_name: str) -> RegistryValidationResult:
        self._profiles.pop(profile_name, None)
        if self._active_profile_name == profile_name and self._profiles:
            self._active_profile_name = sorted(self._profiles)[0]
        self._last_validation = self.validate()
        return self._last_validation

    def rename_profile(self, old_name: str, new_name: str) -> RegistryValidationResult:
        if old_name not in self._profiles:
            self._last_validation = self.validate()
            return self._last_validation
        if new_name in self._profiles and new_name != old_name:
            self._last_validation = self.validate()
            return self._last_validation

        profile = self._profiles.pop(old_name)
        renamed = replace(
            profile,
            profile_name=new_name,
            updated_at=datetime.now(UTC),
        )
        self._profiles[new_name] = renamed
        if self._active_profile_name == old_name:
            self._active_profile_name = new_name
        self._last_validation = self.validate()
        return self._last_validation

    def validate(self) -> RegistryValidationResult:
        self._last_validation = validate_profiles(
            self._profiles,
            active_profile_name=self._active_profile_name,
            api_key_resolver=self._api_key_resolver,
        )
        return self._last_validation

    def resolve_api_key(self, profile: ModelProfile) -> str:
        return self._api_key_resolver(profile.api_key_reference)

    def build_provider_config(self, profile: ModelProfile, api_key: str) -> LLMConfig:
        if profile.provider == "anthropic":
            return replace(
                self._source_config,
                anthropic_api_key=api_key,
                anthropic_model=profile.model,
            )
        return replace(
            self._source_config,
            openai_api_key=api_key,
            openai_base_url=profile.base_url,
            openai_model=profile.model,
        )

    def register_profile(self, profile_name: str, spec: ModelProfileSpec) -> RegistryValidationResult:
        profile = profile_from_spec(profile_name, spec)
        return self.add_profile(profile)

    def export_profiles(self) -> dict[str, ModelProfile]:
        return dict(self._profiles)

    def _load_profiles(self, specs: dict[str, ModelProfileSpec]) -> dict[str, ModelProfile]:
        timestamp = datetime.now(UTC)
        return {
            name: profile_from_spec(name, spec, created_at=timestamp, updated_at=timestamp)
            for name, spec in specs.items()
        }
