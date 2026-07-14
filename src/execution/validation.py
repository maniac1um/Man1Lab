"""Pure validation for execution graphs and task DAGs."""

from __future__ import annotations

from collections import deque

from execution.errors import (
    GraphValidationError,
    TaskDagValidationError,
    UnsupportedStageError,
)
from models.execution_engine import ExecutionTask, ExecutionTaskType
from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType

_SUPPORTED_STAGE_TYPES: frozenset[ExecutionGraphStageType] = frozenset(ExecutionGraphStageType)
_STAGE_TO_TASK_TYPE: dict[ExecutionGraphStageType, ExecutionTaskType] = {
    ExecutionGraphStageType.CLONE_REPOSITORY: ExecutionTaskType.REPOSITORY,
    ExecutionGraphStageType.PREPARE_ENVIRONMENT: ExecutionTaskType.ENVIRONMENT,
    ExecutionGraphStageType.DOWNLOAD_DATASET: ExecutionTaskType.DATASET,
    ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS: ExecutionTaskType.CHECKPOINT,
    ExecutionGraphStageType.GENERATE_CONFIG: ExecutionTaskType.CONFIGURATION,
    ExecutionGraphStageType.TRAINING: ExecutionTaskType.TRAINING,
    ExecutionGraphStageType.EVALUATION: ExecutionTaskType.EVALUATION,
    ExecutionGraphStageType.COMPARISON: ExecutionTaskType.REPORT,
}


def task_type_for_stage(stage_type: ExecutionGraphStageType) -> ExecutionTaskType:
    """Map a planning stage to its canonical execution task type."""
    if stage_type not in _STAGE_TO_TASK_TYPE:
        raise UnsupportedStageError(f"unsupported stage type: {stage_type.value}")
    return _STAGE_TO_TASK_TYPE[stage_type]


def supported_stage_types() -> frozenset[ExecutionGraphStageType]:
    return _SUPPORTED_STAGE_TYPES


def validate_execution_graph(graph: ExecutionGraph) -> None:
    """Validate graph structure without mutating the input."""
    if not graph.graph_id or not graph.strategy_id:
        raise GraphValidationError("graph_id and strategy_id must be non-empty")
    if not graph.nodes:
        raise GraphValidationError("execution graph must contain at least one node")
    node_ids = [node.node_id for node in graph.nodes]
    if len(node_ids) != len(set(node_ids)):
        duplicates = sorted({nid for nid in node_ids if node_ids.count(nid) > 1})
        raise GraphValidationError(f"duplicate node IDs: {', '.join(duplicates)}")

    known_ids = set(node_ids)
    for node in graph.nodes:
        if node.node_id in node.depends_on:
            raise GraphValidationError(f"self-dependency on node {node.node_id}")
        unknown = [dep for dep in node.depends_on if dep not in known_ids]
        if unknown:
            raise GraphValidationError(
                f"node {node.node_id} depends on unknown nodes: {', '.join(unknown)}"
            )
        if node.stage_type not in _SUPPORTED_STAGE_TYPES:
            raise UnsupportedStageError(f"unsupported stage type on node {node.node_id}")
        if node.stage_type not in _STAGE_TO_TASK_TYPE:
            raise UnsupportedStageError(
                f"no task mapping for stage {node.stage_type.value} on node {node.node_id}"
            )

    _assert_acyclic(graph.nodes)


def validate_task_dag(tasks: list[ExecutionTask]) -> None:
    """Validate decomposed task DAG structure."""
    task_ids = [task.id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        duplicates = sorted({tid for tid in task_ids if task_ids.count(tid) > 1})
        raise TaskDagValidationError(f"duplicate task IDs: {', '.join(duplicates)}")

    known_ids = set(task_ids)
    for task in tasks:
        if task.id in task.dependencies:
            raise TaskDagValidationError(f"self-dependency on task {task.id}")
        unknown = [dep for dep in task.dependencies if dep not in known_ids]
        if unknown:
            raise TaskDagValidationError(
                f"task {task.id} depends on unknown tasks: {', '.join(unknown)}"
            )

    _assert_acyclic_tasks(tasks)


def _assert_acyclic(nodes: list[ExecutionGraphNode]) -> None:
    indegree: dict[str, int] = {node.node_id: 0 for node in nodes}
    adjacency: dict[str, list[str]] = {node.node_id: [] for node in nodes}
    for node in nodes:
        for dep in node.depends_on:
            adjacency[dep].append(node.node_id)
            indegree[node.node_id] += 1

    queue: deque[str] = deque(nid for nid, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in adjacency[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if visited != len(nodes):
        raise GraphValidationError("execution graph contains a cycle")


def _assert_acyclic_tasks(tasks: list[ExecutionTask]) -> None:
    indegree: dict[str, int] = {task.id: 0 for task in tasks}
    adjacency: dict[str, list[str]] = {task.id: [] for task in tasks}
    for task in tasks:
        for dep in task.dependencies:
            adjacency[dep].append(task.id)
            indegree[task.id] += 1

    queue: deque[str] = deque(tid for tid, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in adjacency[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if visited != len(tasks):
        raise TaskDagValidationError("task DAG contains a cycle")
