"""Canonical decision trace artifact for discovery and planning stages."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


class DecisionStageName(str, Enum):
    REPOSITORY = "repository"
    EVIDENCE = "evidence"
    VERIFICATION = "verification"
    RANKING = "ranking"
    SELECTION = "selection"
    BINDING = "binding"
    REUSE = "reuse"
    GENERATION = "generation"
    RISK = "risk"


class DecisionStageRecord(BaseModel):
    """One auditable decision point in the pipeline."""

    model_config = ConfigDict(frozen=True)

    stage: DecisionStageName
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    decision_rule: str = ""
    rationale: str = ""
    recorded_at: datetime | None = None


class DecisionTrace(BaseModel):
    """End-to-end trace of important engineering decisions."""

    model_config = ConfigDict(frozen=True)

    trace_id: str
    created_at: datetime
    pipeline_version: str = ""
    discovery_id: str = ""
    strategy_id: str = ""
    stages: list[DecisionStageRecord] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
