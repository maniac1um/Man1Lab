"""Resume foundation logic."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass

from execution.errors import ResumeRejectedError
from execution.transitions import transition_task
from models.execution_engine import (
    DECOMPOSITION_VERSION,
    SCHEMA_VERSION,
    ExecutionRun,
    ExecutionTask,
    ExecutionTaskStatus,
    TaskExecutionResult,
)
from models.execution_graph import ExecutionGraph


@dataclass(frozen=True)
class ResumeEvaluation:
    reusable_task_ids: tuple[str, ...]
    pending_task_ids: tuple[str, ...]
    indeterminate_task_ids: tuple[str, ...]
    rejected_task_ids: tuple[str, ...]
    preserved_statuses: tuple[tuple[str, ExecutionTaskStatus], ...] = ()


def compute_task_fingerprint(tasks: tuple[ExecutionTask, ...]) -> str:
    """Stable fingerprint for decomposition compatibility checks."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "decomposition_version": DECOMPOSITION_VERSION,
        "tasks": [
            {
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "type": task.type.value,
                "dependencies": list(task.dependencies),
                "inputs": [
                    {
                        "logical_name": input_ref.logical_name,
                        "artifact_type": input_ref.artifact_type,
                        "required": input_ref.required,
                        "role": input_ref.role,
                        "artifact_id": input_ref.artifact_id,
                        "integrity_hint": input_ref.integrity_hint,
                    }
                    for input_ref in task.inputs
                ],
                "outputs": [
                    {
                        "logical_name": output.logical_name,
                        "artifact_type": output.artifact_type,
                        "required": output.required,
                        "scope": output.scope.value,
                        "validation_rule": output.validation_rule,
                    }
                    for output in task.outputs
                ],
                "backend_requirements": task.metadata.get("backend_requirements", ""),
                "metadata": {
                    key: value
                    for key, value in sorted(task.metadata.items())
                    if key
                    not in {
                        "source_graph_id",
                        "source_node_id",
                        "decomposition_version",
                        "stage_type",
                    }
                },
            }
            for task in sorted(tasks, key=lambda item: item.id)
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compute_graph_fingerprint(graph: ExecutionGraph) -> str:
    payload = {
        "schema_version": graph.schema_version,
        "decomposition_version": DECOMPOSITION_VERSION,
        "graph_id": graph.graph_id,
        "strategy_id": graph.strategy_id,
        "nodes": [
            {
                "node_id": node.node_id,
                "stage_type": node.stage_type.value,
                "label": node.label,
                "rationale": node.rationale,
                "depends_on": sorted(node.depends_on),
                "binding_ids": sorted(node.binding_ids),
                "asset_ids": sorted(node.asset_ids),
            }
            for node in sorted(graph.nodes, key=lambda item: item.node_id)
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def assert_resume_compatible(
    *,
    existing_run: ExecutionRun,
    graph: ExecutionGraph,
    tasks: tuple[ExecutionTask, ...],
    stored_task_fingerprint: str,
    stored_graph_fingerprint: str,
) -> None:
    """Reject resume when graph or task meaning changed."""
    if existing_run.graph_id != graph.graph_id:
        raise ResumeRejectedError("graph_id mismatch")
    if existing_run.decomposition_version != DECOMPOSITION_VERSION:
        raise ResumeRejectedError("decomposition version mismatch")
    current_task_fp = compute_task_fingerprint(tasks)
    if stored_task_fingerprint and stored_task_fingerprint != current_task_fp:
        raise ResumeRejectedError("task fingerprint mismatch")
    current_graph_fp = compute_graph_fingerprint(graph)
    if stored_graph_fingerprint and stored_graph_fingerprint != current_graph_fp:
        raise ResumeRejectedError("graph fingerprint mismatch")


def evaluate_resume_tasks(
    *,
    tasks: tuple[ExecutionTask, ...],
    prior_results: dict[str, TaskExecutionResult],
    artifact_valid: Callable[[str], bool] | None = None,
    result_outputs_valid: Callable[[ExecutionTask, TaskExecutionResult], bool] | None = None,
) -> ResumeEvaluation:
    """Classify tasks for resume without auto-dispatching indeterminate work."""
    reusable: list[str] = []
    pending: list[str] = []
    indeterminate: list[str] = []
    rejected: list[str] = []
    preserved: list[tuple[str, ExecutionTaskStatus]] = []

    for task in tasks:
        prior = prior_results.get(task.id)
        if prior is None:
            pending.append(task.id)
            continue
        if prior.status == ExecutionTaskStatus.SUCCESS:
            valid = (
                result_outputs_valid(task, prior)
                if result_outputs_valid is not None
                else _success_still_valid(prior, artifact_valid)
            )
            if valid:
                reusable.append(task.id)
            else:
                rejected.append(task.id)
                pending.append(task.id)
        elif prior.status == ExecutionTaskStatus.RUNNING:
            indeterminate.append(task.id)
        elif prior.status in {
            ExecutionTaskStatus.PENDING,
            ExecutionTaskStatus.READY,
        }:
            pending.append(task.id)
        elif prior.status in {
            ExecutionTaskStatus.FAILED,
            ExecutionTaskStatus.SKIPPED,
            ExecutionTaskStatus.CANCELLED,
        }:
            preserved.append((task.id, prior.status))

    return ResumeEvaluation(
        reusable_task_ids=tuple(reusable),
        pending_task_ids=tuple(pending),
        indeterminate_task_ids=tuple(indeterminate),
        rejected_task_ids=tuple(rejected),
        preserved_statuses=tuple(preserved),
    )


def apply_resume_reuse(
    tasks: tuple[ExecutionTask, ...],
    evaluation: ResumeEvaluation,
) -> tuple[ExecutionTask, ...]:
    """Mark reusable successful tasks; keep indeterminate tasks RUNNING."""
    reusable = set(evaluation.reusable_task_ids)
    indeterminate = set(evaluation.indeterminate_task_ids)
    preserved = dict(evaluation.preserved_statuses)
    updated: list[ExecutionTask] = []
    for task in tasks:
        if task.id in reusable:
            updated.append(
                transition_task(task, ExecutionTaskStatus.SUCCESS, recovery=True)
            )
        elif task.id in indeterminate:
            updated.append(
                transition_task(task, ExecutionTaskStatus.RUNNING, recovery=True)
            )
        elif task.id in preserved:
            updated.append(transition_task(task, preserved[task.id], recovery=True))
        else:
            updated.append(task)
    return tuple(updated)


def _success_still_valid(
    result: TaskExecutionResult,
    artifact_valid: Callable[[str], bool] | None,
) -> bool:
    if result.status != ExecutionTaskStatus.SUCCESS:
        return False
    if not result.artifact_ids:
        return False
    return artifact_valid is not None and all(
        artifact_valid(artifact_id) for artifact_id in result.artifact_ids
    )

