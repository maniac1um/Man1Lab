"""Hydra-backed settings provider."""

from __future__ import annotations

from pathlib import Path

from omegaconf import DictConfig

from configuration.models import (
    AppSettings,
    DiscoveryConfig,
    ExecutionPlanningConfig,
    LLMConfig,
    LoggingConfig,
    ModelProfileSpec,
    ParserConfig,
    TrackingConfig,
    WorkflowConfig,
)
from configuration.provider import SettingsProvider


class HydraSettingsProvider:
    def __init__(self, cfg: DictConfig) -> None:
        self._cfg = cfg
        self._settings = _settings_from_config(cfg)

    def get_settings(self) -> AppSettings:
        return self._settings


def _settings_from_config(cfg: DictConfig) -> AppSettings:
    return AppSettings(
        workspace_root=Path(cfg.workspace_root),
        outputs_dir=Path(cfg.outputs_dir),
        logs_dir=Path(cfg.logs_dir),
        prompts_dir=Path(cfg.prompts_dir),
        paper_path=Path(cfg.paper_path),
        parser=ParserConfig(
            backend=str(cfg.parser.backend),
            max_paper_text_chars=int(cfg.parser.max_paper_text_chars),
        ),
        discovery=DiscoveryConfig(
            enabled=bool(cfg.discovery.enabled),
        ),
        execution_planning=ExecutionPlanningConfig(
            enabled=bool(cfg.execution_planning.enabled),
        ),
        workflow=WorkflowConfig(
            max_review_iterations=int(cfg.workflow.max_review_iterations),
        ),
        llm=_merge_persisted_llm_config(_llm_config_from_hydra(cfg.llm)),
        logging=LoggingConfig(
            level=str(cfg.logging.level),
            format=str(cfg.logging.format),
        ),
        tracking=TrackingConfig(
            enabled=bool(cfg.tracking.enabled),
            backend=str(cfg.tracking.backend),
            experiment_name=str(cfg.tracking.experiment_name),
            tracking_uri=str(cfg.tracking.tracking_uri),
        ),
    )


def _llm_config_from_hydra(cfg: object) -> LLMConfig:
    profiles_cfg = getattr(cfg, "profiles", None)
    profiles: dict[str, ModelProfileSpec] | None = None
    if profiles_cfg is not None:
        profiles = {}
        for name, profile in profiles_cfg.items():
            tags_raw = getattr(profile, "tags", ()) or ()
            temperature = getattr(profile, "temperature", None)
            max_tokens = getattr(profile, "max_tokens", None)
            profiles[str(name)] = ModelProfileSpec(
                provider=str(profile.provider),
                model=str(profile.model),
                base_url=str(getattr(profile, "base_url", "") or ""),
                api_key_reference=str(
                    getattr(profile, "api_key_reference", "OPENAI_API_KEY") or "OPENAI_API_KEY"
                ),
                organization=str(getattr(profile, "organization", "") or ""),
                api_version=str(getattr(profile, "api_version", "") or ""),
                temperature=float(temperature) if temperature is not None else None,
                max_tokens=int(max_tokens) if max_tokens is not None else None,
                enabled=bool(getattr(profile, "enabled", True)),
                description=str(getattr(profile, "description", "") or ""),
                tags=tuple(str(tag) for tag in tags_raw),
            )

    return LLMConfig(
        active=str(getattr(cfg, "active", "default") or "default"),
        profiles=profiles,
        openai_api_key=str(cfg.openai_api_key),
        openai_base_url=str(cfg.openai_base_url),
        openai_model=str(cfg.openai_model),
        anthropic_api_key=str(cfg.anthropic_api_key),
        anthropic_model=str(cfg.anthropic_model),
    )


def _merge_persisted_llm_config(base: LLMConfig) -> LLMConfig:
    from configuration.paths import resolve_llm_user_profiles_path
    from providers.llm.persistence import load_persisted_llm_config, merge_llm_config

    overlay = load_persisted_llm_config(resolve_llm_user_profiles_path())
    return merge_llm_config(base, overlay)
