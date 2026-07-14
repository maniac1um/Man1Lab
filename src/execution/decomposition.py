"""Deterministic ExecutionGraph → ExecutionTask decomposition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from execution.validation import task_type_for_stage, validate_execution_graph, validate_task_dag
from execution_materialization.task_factory import merge_metadata
from models.execution_engine import (
    DECOMPOSITION_VERSION,
    ExecutionArtifactReference,
    ExecutionTask,
    ExecutionTaskStatus,
    OutputDeclaration,
    TraceEvent,
    TraceEventType,
)
from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType


def task_id_for_node(node_id: str) -> str:
    """Deterministic task ID for a graph node."""
    return f"task-{node_id}"


@dataclass(frozen=True)
class DecompositionResult:
    tasks: tuple[ExecutionTask, ...]
    events: tuple[TraceEvent, ...]
    source_graph_id: str


def _default_outputs(stage_type: ExecutionGraphStageType) -> tuple[OutputDeclaration, ...]:
    mapping: dict[ExecutionGraphStageType, tuple[OutputDeclaration, ...]] = {
        ExecutionGraphStageType.CLONE_REPOSITORY: (
            OutputDeclaration(logical_name="repository", artifact_type="repository", required=True),
        ),
        ExecutionGraphStageType.PREPARE_ENVIRONMENT: (
            OutputDeclaration(logical_name="environment", artifact_type="environment", required=True),
        ),
        ExecutionGraphStageType.DOWNLOAD_DATASET: (
            OutputDeclaration(logical_name="dataset", artifact_type="dataset", required=True),
        ),
        ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS: (
            OutputDeclaration(logical_name="checkpoint", artifact_type="checkpoint", required=True),
        ),
        ExecutionGraphStageType.GENERATE_CONFIG: (
            OutputDeclaration(logical_name="configuration", artifact_type="configuration", required=True),
        ),
        ExecutionGraphStageType.TRAINING: (
            OutputDeclaration(logical_name="training_output", artifact_type="training", required=True),
        ),
        ExecutionGraphStageType.EVALUATION: (
            OutputDeclaration(logical_name="evaluation_output", artifact_type="evaluation", required=True),
        ),
        ExecutionGraphStageType.COMPARISON: (
            OutputDeclaration(logical_name="report", artifact_type="report", required=True),
        ),
    }
    return mapping[stage_type]


def _inputs_for_node(node: ExecutionGraphNode) -> tuple[ExecutionArtifactReference, ...]:
    refs: list[ExecutionArtifactReference] = []
    for binding_id in node.binding_ids:
        refs.append(
            ExecutionArtifactReference(
                logical_name=f"binding:{binding_id}",
                artifact_type="binding",
                required=node.execution_spec is None,
                role="binding",
            )
        )
    for asset_id in node.asset_ids:
        refs.append(
            ExecutionArtifactReference(
                logical_name=f"asset:{asset_id}",
                artifact_type="asset",
                required=False,
                role="asset",
            )
        )
    return tuple(refs)


def decompose_execution_graph(
    graph: ExecutionGraph,
    *,
    run_id: str,
    sequence_start: int = 0,
    recorded_at: datetime | None = None,
) -> DecompositionResult:
    """Translate an immutable graph into canonical tasks without mutating the graph."""
    validate_execution_graph(graph)
    now = recorded_at or datetime.now(UTC)
    node_to_task = {node.node_id: task_id_for_node(node.node_id) for node in graph.nodes}

    tasks: list[ExecutionTask] = []
    events: list[TraceEvent] = []
    sequence = sequence_start

    for node in graph.nodes:
        task_type = task_type_for_stage(node.stage_type)
        base_metadata = {
            "source_graph_id": graph.graph_id,
            "source_node_id": node.node_id,
            "decomposition_version": DECOMPOSITION_VERSION,
            "stage_type": node.stage_type.value,
            "binding_ids": ",".join(node.binding_ids),
            "asset_ids": ",".join(node.asset_ids),
        }
        if node.execution_spec is not None:
            metadata = merge_metadata(base_metadata, node.execution_spec)
        else:
            metadata = base_metadata
        task = ExecutionTask(
            id=node_to_task[node.node_id],
            name=node.label,
            type=task_type,
            description=node.rationale or node.label,
            dependencies=tuple(node_to_task[dep] for dep in node.depends_on),
            inputs=_inputs_for_node(node),
            outputs=_default_outputs(node.stage_type),
            status=ExecutionTaskStatus.PENDING,
            metadata=metadata,
        )
        tasks.append(task)
        events.append(
            TraceEvent(
                event_id=f"evt-{run_id}-created-{task.id}",
                event_type=TraceEventType.TASK_CREATED,
                run_id=run_id,
                sequence=sequence,
                recorded_at=now,
                task_id=task.id,
                actor="decomposition",
                payload={
                    "task_type": task.type.value,
                    "source_graph_id": graph.graph_id,
                    "source_node_id": node.node_id,
                    "dependency_count": str(len(task.dependencies)),
                },
            )
        )
        sequence += 1

    validate_task_dag(tasks)
    return DecompositionResult(
        tasks=tuple(tasks),
        events=tuple(events),
        source_graph_id=graph.graph_id,
    )
