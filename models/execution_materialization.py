"""Canonical planning-to-execution materialization models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.executable_task_spec import ExecutableTaskSpec
from models.execution_graph import ExecutionGraph

SCHEMA_VERSION = "1.0"


class MaterializationStatus(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"


class MaterializationIssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class MaterializationIssue(BaseModel):
    """Structured materialization diagnostic."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    severity: MaterializationIssueSeverity = MaterializationIssueSeverity.ERROR
    node_id: str | None = None
    stage_type: str | None = None
    template_id: str | None = None


class NodeMaterializationResult(BaseModel):
    """Per-node materialization outcome."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    stage_type: str
    status: MaterializationStatus
    template_id: str | None = None
    template_version: str | None = None
    issues: tuple[MaterializationIssue, ...] = Field(default_factory=tuple)


class MaterializationReport(BaseModel):
    """Readiness report for a materialized execution graph."""

    model_config = ConfigDict(frozen=True)

    status: MaterializationStatus
    node_results: tuple[NodeMaterializationResult, ...] = Field(default_factory=tuple)
    errors: tuple[MaterializationIssue, ...] = Field(default_factory=tuple)
    warnings: tuple[MaterializationIssue, ...] = Field(default_factory=tuple)
    required_capabilities: tuple[str, ...] = Field(default_factory=tuple)
    resolved_references: dict[str, str] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def _status_consistency(self) -> MaterializationReport:
        if self.status is MaterializationStatus.READY:
            if not self.node_results:
                raise ValueError("READY report requires node_results")
            blocking = [
                issue
                for issue in (*self.errors, *(issue for nr in self.node_results for issue in nr.issues))
                if issue.severity is MaterializationIssueSeverity.ERROR
            ]
            if blocking:
                raise ValueError("READY report cannot contain blocking errors")
            not_ready = [nr for nr in self.node_results if nr.status is not MaterializationStatus.READY]
            if not_ready:
                raise ValueError("READY report requires all node_results to be READY")
        return self


class ExecutionMaterialization(BaseModel):
    """Canonical output of the materialization capability."""

    model_config = ConfigDict(frozen=True)

    materialization_id: str
    strategy_id: str
    graph_id: str
    discovery_id: str | None = None
    analysis_id: str | None = None
    backend_kind: str = "local"
    materialized_graph: ExecutionGraph
    report: MaterializationReport
    created_at: datetime
    schema_version: str = SCHEMA_VERSION

    @field_validator("created_at")
    @classmethod
    def _utc_only(cls, value: datetime) -> datetime:
        from datetime import timedelta

        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("created_at must use UTC")
        return value


__all__ = [
    "ExecutableTaskSpec",
    "ExecutionMaterialization",
    "MaterializationIssue",
    "MaterializationIssueSeverity",
    "MaterializationReport",
    "MaterializationStatus",
    "NodeMaterializationResult",
    "SCHEMA_VERSION",
]
