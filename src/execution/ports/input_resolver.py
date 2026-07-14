"""Input resolver port contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from models.execution_engine import ExecutionArtifactReference, ExecutionTask, TaskExecutionResult


@dataclass(frozen=True)
class ResolvedInput:
    logical_name: str
    artifact_id: str
    artifact_type: str
    required: bool
    valid: bool
    role: str = ""
    diagnostic: str = ""


@dataclass(frozen=True)
class InputResolutionResult:
    inputs: tuple[ResolvedInput, ...]
    ready: bool
    blocking_reason: str = ""


class InputResolverPort(Protocol):
    """Resolves declared task inputs without filesystem access."""

    def resolve_inputs(
        self,
        *,
        run_id: str,
        task: ExecutionTask,
        prior_results: dict[str, TaskExecutionResult],
    ) -> InputResolutionResult:
        """Resolve declared inputs for readiness and dispatch."""
