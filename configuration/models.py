"""Application configuration models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParserConfig:
    backend: str = "docling"
    max_paper_text_chars: int = 80_000


@dataclass(frozen=True)
class DiscoveryConfig:
    enabled: bool = True


@dataclass(frozen=True)
class ExecutionPlanningConfig:
    enabled: bool = True


@dataclass(frozen=True)
class WorkflowConfig:
    max_review_iterations: int = 3


@dataclass(frozen=True)
class ModelProfileSpec:
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


@dataclass(frozen=True)
class LLMConfig:
    active: str = "default"
    profiles: dict[str, ModelProfileSpec] | None = None
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"
    llm_connect_timeout_seconds: float = 60.0
    llm_read_timeout_seconds: float = 600.0
    llm_write_timeout_seconds: float = 600.0
    llm_pool_timeout_seconds: float = 60.0


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s %(levelname)s %(message)s"


@dataclass(frozen=True)
class TrackingConfig:
    enabled: bool = False
    backend: str = "noop"
    experiment_name: str = "man1lab"
    tracking_uri: str = "sqlite:///mlruns/mlflow.db"


@dataclass(frozen=True)
class AppSettings:
    workspace_root: Path
    outputs_dir: Path
    logs_dir: Path
    prompts_dir: Path
    paper_path: Path
    parser: ParserConfig
    discovery: DiscoveryConfig
    execution_planning: ExecutionPlanningConfig
    workflow: WorkflowConfig
    llm: LLMConfig
    logging: LoggingConfig
    tracking: TrackingConfig
