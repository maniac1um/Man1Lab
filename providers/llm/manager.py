"""LLM manager — single entry for provider-backed inference."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from configuration.models import LLMConfig
from configuration.paths import resolve_llm_user_profiles_path
from providers.llm.base import LLMProvider
from providers.llm.model_management import (
    CurrentModelReport,
    ModelChangeReport,
    ModelListReport,
    ModelTestReport,
    add_model_profile,
    build_current_model_report,
    build_model_list_report,
    persist_registry,
    test_model_profile,
)
from providers.llm.persistence import ModelImportReport, export_portable_config, import_portable_config
from providers.llm.models import LLMHealthStatus, LLMMessage, RegistryValidationResult
from providers.llm.provider_registry import ProviderRegistry, create_default_registry
from providers.llm.registry import ModelRegistry


class LLMManager:
    """Resolve the active profile and delegate inference to the selected provider."""

    def __init__(
        self,
        config: LLMConfig,
        *,
        model_registry: ModelRegistry | None = None,
        provider_registry: ProviderRegistry | None = None,
        persistence_path: Path | None = None,
    ) -> None:
        self._config = config
        self._persistence_path = persistence_path or resolve_llm_user_profiles_path()
        self._model_registry = model_registry or ModelRegistry(config)
        self._provider_registry = provider_registry or create_default_registry()
        self._provider = self._resolve_provider()

    @classmethod
    def from_legacy_config(
        cls,
        *,
        provider_registry: ProviderRegistry | None = None,
    ) -> LLMManager:
        import config as legacy_config
        from configuration.models import LLMConfig

        return cls(
            LLMConfig(
                openai_api_key=legacy_config.OPENAI_API_KEY or "",
                openai_base_url=legacy_config.OPENAI_BASE_URL or "",
                openai_model=legacy_config.OPENAI_MODEL or "gpt-4o-mini",
                anthropic_api_key=legacy_config.ANTHROPIC_API_KEY or "",
                anthropic_model=legacy_config.ANTHROPIC_MODEL or "claude-3-5-haiku-latest",
            ),
            provider_registry=provider_registry,
        )

    @property
    def model_registry(self) -> ModelRegistry:
        return self._model_registry

    @property
    def active_profile_name(self) -> str | None:
        profile = self._model_registry.get_active_profile()
        if profile is None or not self._model_registry.last_validation.valid:
            return None
        return profile.profile_name

    @property
    def active_provider_name(self) -> str | None:
        profile = self._model_registry.get_active_profile()
        if profile is None or self._provider is None:
            return None
        return profile.provider

    def has_active_provider(self) -> bool:
        return self._provider is not None

    def get_provider(self) -> LLMProvider:
        if self._provider is None:
            raise RuntimeError("No active LLM provider is configured.")
        return self._provider

    def list_available_providers(self) -> list[str]:
        return self._provider_registry.list_providers()

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> str:
        profile = self._model_registry.get_active_profile()
        resolved_temperature = (
            profile.temperature if profile is not None and profile.temperature is not None else temperature
        )
        resolved_model = model or (profile.model if profile is not None else None)
        resolved_max_tokens = profile.max_tokens if profile is not None else None
        return self.get_provider().generate(
            messages,
            temperature=resolved_temperature,
            model=resolved_model,
            max_tokens=resolved_max_tokens,
        )

    def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> Iterator[str]:
        profile = self._model_registry.get_active_profile()
        resolved_temperature = (
            profile.temperature if profile is not None and profile.temperature is not None else temperature
        )
        resolved_model = model or (profile.model if profile is not None else None)
        return self.get_provider().stream(
            messages,
            temperature=resolved_temperature,
            model=resolved_model,
        )

    def health_check(self) -> LLMHealthStatus:
        return self.get_provider().health_check()

    def list_models(self) -> ModelListReport:
        return build_model_list_report(self._model_registry)

    def current_model(self) -> CurrentModelReport | None:
        return build_current_model_report(self._model_registry)

    def use_model(self, profile_name: str) -> ModelChangeReport:
        validation = self._model_registry.set_active_profile(profile_name)
        if not validation.valid:
            return ModelChangeReport(
                successful=False,
                message=f"Could not activate profile '{profile_name}'.",
                validation=validation,
            )
        self._refresh_provider()
        self._persist_registry()
        return ModelChangeReport(
            successful=True,
            message="Active profile changed",
            active_profile=profile_name,
            validation=validation,
        )

    def add_model(
        self,
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
    ) -> ModelChangeReport:
        validation = add_model_profile(
            self._model_registry,
            profile_name=profile_name,
            provider=provider,
            model=model,
            base_url=base_url,
            api_key_reference=api_key_reference,
            temperature=temperature,
            max_tokens=max_tokens,
            description=description,
            enabled=enabled,
        )
        if not validation.valid:
            return ModelChangeReport(
                successful=False,
                message=f"Could not add profile '{profile_name}'.",
                validation=validation,
            )
        self._persist_registry()
        return ModelChangeReport(
            successful=True,
            message=f"Profile '{profile_name}' added.",
            active_profile=self._model_registry.active_profile_name,
            validation=validation,
        )

    def remove_model(self, profile_name: str, *, force: bool = False) -> ModelChangeReport:
        if (
            profile_name == self._model_registry.active_profile_name
            and not force
        ):
            return ModelChangeReport(
                successful=False,
                message=(
                    f"Cannot remove active profile '{profile_name}' without --force."
                ),
            )
        if self._model_registry.get_profile(profile_name) is None:
            return ModelChangeReport(
                successful=False,
                message=f"Profile '{profile_name}' was not found.",
            )
        validation = self._model_registry.remove_profile(profile_name)
        self._refresh_provider()
        self._persist_registry()
        return ModelChangeReport(
            successful=True,
            message=f"Profile '{profile_name}' removed.",
            active_profile=self._model_registry.active_profile_name,
            validation=validation,
        )

    def rename_model(self, old_name: str, new_name: str) -> ModelChangeReport:
        if self._model_registry.get_profile(old_name) is None:
            return ModelChangeReport(
                successful=False,
                message=f"Profile '{old_name}' was not found.",
            )
        validation = self._model_registry.rename_profile(old_name, new_name)
        if not validation.valid:
            return ModelChangeReport(
                successful=False,
                message=f"Could not rename profile '{old_name}' to '{new_name}'.",
                validation=validation,
            )
        self._persist_registry()
        return ModelChangeReport(
            successful=True,
            message=f"Profile renamed to '{new_name}'.",
            active_profile=self._model_registry.active_profile_name,
            validation=validation,
        )

    def test_model(self, profile_name: str | None = None) -> ModelTestReport:
        return test_model_profile(
            self._model_registry,
            self._provider_registry,
            profile_name=profile_name,
        )

    def validate_models(self) -> RegistryValidationResult:
        return self._model_registry.validate()

    def export_models(self, path: Path) -> Path:
        return export_portable_config(
            self._model_registry.export_profiles(),
            active=self._model_registry.active_profile_name,
            base_config=self._config,
            path=path,
        )

    def import_models(
        self,
        path: Path,
        *,
        replace: bool = False,
        skip_existing: bool = False,
    ) -> ModelImportReport:
        report = import_portable_config(
            self._model_registry,
            path,
            replace=replace,
            skip_existing=skip_existing,
        )
        if report.successful:
            self._refresh_provider()
            self._persist_registry()
        return report

    def _refresh_provider(self) -> None:
        self._provider = self._resolve_provider()

    def _persist_registry(self) -> Path:
        return persist_registry(
            self._model_registry,
            self._config,
            path=self._persistence_path,
        )

    def _resolve_provider(self) -> LLMProvider | None:
        validation = self._model_registry.validate()
        if not validation.valid:
            return None

        profile = self._model_registry.get_active_profile()
        if profile is None or not profile.enabled:
            return None

        api_key = self._model_registry.resolve_api_key(profile)
        if not api_key:
            return None

        provider_config = self._model_registry.build_provider_config(profile, api_key)
        try:
            return self._provider_registry.resolve(profile.provider, provider_config)
        except (KeyError, ValueError):
            return None
