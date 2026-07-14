"""Artifact tracker port contract."""

from __future__ import annotations

from typing import Protocol

from execution.ports.executor import ArtifactCandidate
from models.execution_engine import Artifact, ArtifactScope, ExecutionTask, OutputDeclaration, TaskExecutionResult


class ArtifactTrackerPort(Protocol):
    """Registers and validates execution artifacts."""

    def register_candidate(
        self,
        *,
        run_id: str,
        task_id: str,
        attempt_id: str,
        candidate: ArtifactCandidate,
        scope: ArtifactScope = ArtifactScope.RUNTIME_RUN,
    ) -> Artifact:
        """Register an executor-produced artifact candidate (registered, not yet validated)."""

    def validate_required_outputs(
        self,
        *,
        run_id: str,
        task_id: str,
        attempt_id: str,
        declarations: tuple[OutputDeclaration, ...],
    ) -> tuple[Artifact, ...]:
        """Validate required outputs for one run/task/attempt scope."""

    def get_artifact(self, artifact_id: str) -> Artifact | None:
        """Return a registered artifact by ID."""

    def invalidate(self, artifact_id: str, *, reason: str = "") -> Artifact:
        """Mark an artifact invalid."""

    def list_artifacts_for_task(
        self,
        task_id: str,
        *,
        run_id: str | None = None,
    ) -> tuple[Artifact, ...]:
        """Return artifacts produced by a task, optionally scoped to a run."""

    def list_artifacts_for_attempt(
        self,
        *,
        run_id: str,
        task_id: str,
        attempt_id: str,
    ) -> tuple[Artifact, ...]:
        """Return artifacts for one attempt scope."""

    def artifact_still_valid(self, artifact_id: str) -> bool:
        """Return whether a registered artifact remains valid."""

    def result_satisfies_required_outputs(
        self,
        *,
        run_id: str,
        task: ExecutionTask,
        result: TaskExecutionResult,
    ) -> bool:
        """Return whether a prior result still satisfies the task output contract."""

