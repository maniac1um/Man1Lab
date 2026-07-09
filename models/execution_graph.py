"""Execution-oriented graph produced by planning for a future execution engine."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


class ExecutionGraphStageType(str, Enum):
    CLONE_REPOSITORY = "clone_repository"
    PREPARE_ENVIRONMENT = "prepare_environment"
    DOWNLOAD_DATASET = "download_dataset"
    DOWNLOAD_CHECKPOINTS = "download_checkpoints"
    GENERATE_CONFIG = "generate_config"
    TRAINING = "training"
    EVALUATION = "evaluation"
    COMPARISON = "comparison"


class ExecutionGraphNode(BaseModel):
    """Single deterministic stage in the execution graph."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    stage_type: ExecutionGraphStageType
    label: str
    depends_on: list[str] = Field(default_factory=list)
    binding_ids: list[str] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class ExecutionGraph(BaseModel):
    """Ordered execution graph derived from strategy and discovery assets."""

    model_config = ConfigDict(frozen=True)

    graph_id: str
    created_at: datetime
    strategy_id: str
    nodes: list[ExecutionGraphNode] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
