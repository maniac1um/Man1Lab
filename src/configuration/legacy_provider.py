"""Legacy settings provider backed by environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from configuration.models import (
    AppSettings,
    DiscoveryConfig,
    ExecutionPlanningConfig,
    LLMConfig,
    LoggingConfig,
    ParserConfig,
    WorkflowConfig,
    TrackingConfig,
)
from configuration.provider import SettingsProvider


class LegacySettingsProvider:
    """Load settings from environment variables (pre-Hydra behavior)."""

    def __init__(self) -> None:
        load_dotenv()

    def get_settings(self) -> AppSettings:
        return AppSettings(
            workspace_root=Path("workspace/tasks"),
            outputs_dir=Path("outputs"),
            logs_dir=Path("logs"),
            prompts_dir=Path("prompts"),
            paper_path=Path(os.getenv("PAPER_PATH", "paper.pdf")),
            parser=ParserConfig(
                backend=os.getenv("PARSER_BACKEND", "docling"),
                max_paper_text_chars=int(os.getenv("MAX_PAPER_TEXT_CHARS", "80000")),
            ),
            discovery=DiscoveryConfig(
                enabled=os.getenv("DISCOVERY_ENABLED", "true").lower() == "true",
            ),
            execution_planning=ExecutionPlanningConfig(
                enabled=os.getenv("EXECUTION_PLANNING_ENABLED", "true").lower() == "true",
            ),
            workflow=WorkflowConfig(
                max_review_iterations=int(os.getenv("MAX_REVIEW_ITERATIONS", "3")),
            ),
            llm=LLMConfig(
                openai_api_key=os.getenv("OPENAI_API_KEY", ""),
                openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
                openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                anthropic_model=os.getenv(
                    "ANTHROPIC_MODEL", "claude-3-5-haiku-latest"
                ),
            ),
            logging=LoggingConfig(),
            tracking=TrackingConfig(
                enabled=os.getenv("TRACKING_ENABLED", "false").lower() == "true",
                backend=os.getenv("TRACKING_BACKEND", "noop"),
                experiment_name=os.getenv("MLFLOW_EXPERIMENT_NAME", "man1lab"),
                tracking_uri=os.getenv(
                    "MLFLOW_TRACKING_URI", "sqlite:///mlruns/mlflow.db"
                ),
            ),
        )


def get_settings() -> AppSettings:
    return LegacySettingsProvider().get_settings()
