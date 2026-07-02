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
        llm=LLMConfig(
            openai_api_key=str(cfg.llm.openai_api_key),
            openai_base_url=str(cfg.llm.openai_base_url),
            openai_model=str(cfg.llm.openai_model),
            anthropic_api_key=str(cfg.llm.anthropic_api_key),
            anthropic_model=str(cfg.llm.anthropic_model),
        ),
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
