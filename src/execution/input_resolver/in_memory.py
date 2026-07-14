"""In-memory input resolver for tests."""

from __future__ import annotations

from execution.ports.artifacts import ArtifactTrackerPort
from execution.ports.input_resolver import InputResolutionResult, ResolvedInput
from models.execution_engine import ExecutionTask, ExecutionTaskStatus, TaskExecutionResult


class InMemoryInputResolver:
    """Resolves task inputs from prior results and the artifact tracker."""

    def __init__(self, artifact_tracker: ArtifactTrackerPort) -> None:
        self._artifact_tracker = artifact_tracker

    def resolve_inputs(
        self,
        *,
        run_id: str,
        task: ExecutionTask,
        prior_results: dict[str, TaskExecutionResult],
    ) -> InputResolutionResult:
        resolved: list[ResolvedInput] = []
        blocking: list[str] = []

        for input_ref in task.inputs:
            artifact_id = input_ref.artifact_id
            valid = False
            diagnostic = ""

            if not artifact_id:
                if input_ref.required:
                    diagnostic = f"required input {input_ref.logical_name} has empty artifact_id"
                    blocking.append(diagnostic)
                resolved.append(
                    ResolvedInput(
                        logical_name=input_ref.logical_name,
                        artifact_id="",
                        artifact_type=input_ref.artifact_type,
                        required=input_ref.required,
                        valid=False,
                        role=input_ref.role,
                        diagnostic=diagnostic or "optional input unresolved",
                    )
                )
                continue

            artifact = self._artifact_tracker.get_artifact(artifact_id)
            if artifact is None:
                diagnostic = f"artifact {artifact_id} not found"
            elif artifact.producer_run_id != run_id:
                diagnostic = f"artifact {artifact_id} belongs to another run"
            elif artifact.validation_state.value != "valid":
                if artifact.validation_state.value == "invalid":
                    diagnostic = f"artifact {artifact_id} invalidated"
                else:
                    diagnostic = f"artifact {artifact_id} not validated"
            elif artifact.artifact_type != input_ref.artifact_type:
                diagnostic = (
                    f"artifact {artifact_id} type mismatch: expected {input_ref.artifact_type}, "
                    f"got {artifact.artifact_type}"
                )
            else:
                valid = True

            if input_ref.required and not valid:
                blocking.append(diagnostic or f"required input {input_ref.logical_name} unavailable")

            resolved.append(
                ResolvedInput(
                    logical_name=input_ref.logical_name,
                    artifact_id=artifact_id,
                    artifact_type=input_ref.artifact_type,
                    required=input_ref.required,
                    valid=valid,
                    role=input_ref.role,
                    diagnostic=diagnostic,
                )
            )

        for dep_id in task.dependencies:
            dep_result = prior_results.get(dep_id)
            if dep_result is None or dep_result.status != ExecutionTaskStatus.SUCCESS:
                blocking.append(f"dependency {dep_id} not successful")

        ready = not blocking
        return InputResolutionResult(
            inputs=tuple(resolved),
            ready=ready,
            blocking_reason="; ".join(blocking),
        )
