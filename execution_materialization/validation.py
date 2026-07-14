"""Readiness validation for materialized execution graphs."""

from __future__ import annotations

from models.execution_preparation import PreparationRequest
from models.execution_graph import ExecutionGraph, ExecutionGraphStageType
from models.execution_materialization import (
    MaterializationIssue,
    MaterializationIssueSeverity,
    MaterializationReport,
    MaterializationStatus,
    NodeMaterializationResult,
)


class ExecutionReadinessValidator:
    """Validate complete materialized graphs before execution."""

    def validate(
        self,
        graph: ExecutionGraph,
        *,
        node_results: tuple[NodeMaterializationResult, ...],
        resolved_references: dict[str, str],
        warnings: tuple[MaterializationIssue, ...] = (),
    ) -> MaterializationReport:
        errors: list[MaterializationIssue] = []
        capabilities: set[str] = {"local"}

        if not graph.materialization_id:
            errors.append(
                MaterializationIssue(
                    code="missing_materialization_id",
                    message="graph is missing materialization_id",
                    severity=MaterializationIssueSeverity.ERROR,
                )
            )

        graph_node_ids = {node.node_id for node in graph.nodes}
        result_node_ids = {result.node_id for result in node_results}
        if graph_node_ids != result_node_ids:
            errors.append(
                MaterializationIssue(
                    code="node_result_mismatch",
                    message="materialization node results do not exactly cover the graph",
                    severity=MaterializationIssueSeverity.ERROR,
                )
            )

        repository_producers: dict[str, str] = {}

        for node in graph.nodes:
            if node.execution_spec is None:
                errors.append(
                    MaterializationIssue(
                        code="missing_execution_spec",
                        message="executable node is missing execution_spec",
                        severity=MaterializationIssueSeverity.ERROR,
                        node_id=node.node_id,
                        stage_type=node.stage_type.value,
                    )
                )
                continue
            expected_output = _EXPECTED_OUTPUTS[node.stage_type]
            if set(node.execution_spec.artifact_paths) != {expected_output}:
                errors.append(
                    MaterializationIssue(
                        code="artifact_contract_mismatch",
                        message=f"artifact_paths must declare exactly: {expected_output}",
                        severity=MaterializationIssueSeverity.ERROR,
                        node_id=node.node_id,
                        stage_type=node.stage_type.value,
                    )
                )
            request = _preparation_request(node.execution_spec.command)
            if node.stage_type in _PREPARATION_STAGES and request is None:
                errors.append(
                    MaterializationIssue(
                        code="invalid_preparation_request",
                        message="preparation task is missing a typed request",
                        severity=MaterializationIssueSeverity.ERROR,
                        node_id=node.node_id,
                        stage_type=node.stage_type.value,
                    )
                )
            if node.stage_type is ExecutionGraphStageType.CLONE_REPOSITORY and request is not None:
                repository_producers[request.target_path] = node.node_id

        for node in graph.nodes:
            spec = node.execution_spec
            if spec is None or node.stage_type in _PREPARATION_STAGES:
                continue
            producer_id = repository_producers.get(spec.working_directory)
            if producer_id is not None and producer_id not in _ancestor_ids(graph, node.node_id):
                errors.append(
                    MaterializationIssue(
                        code="future_reference_without_producer_dependency",
                        message="working directory is produced by a repository task that is not an ancestor",
                        severity=MaterializationIssueSeverity.ERROR,
                        node_id=node.node_id,
                        stage_type=node.stage_type.value,
                    )
                )

        blocking_node_results = [item for item in node_results if item.status is not MaterializationStatus.READY]
        for item in blocking_node_results:
            for issue in item.issues:
                if issue.severity is MaterializationIssueSeverity.ERROR:
                    errors.append(issue)

        status = MaterializationStatus.READY
        if any(issue.severity is MaterializationIssueSeverity.ERROR for issue in errors):
            if any(item.status is MaterializationStatus.UNSUPPORTED for item in node_results):
                status = MaterializationStatus.UNSUPPORTED
            else:
                status = MaterializationStatus.BLOCKED
        elif blocking_node_results:
            status = MaterializationStatus.BLOCKED

        return MaterializationReport(
            status=status,
            node_results=node_results,
            errors=tuple(errors),
            warnings=warnings,
            required_capabilities=tuple(sorted(capabilities)),
            resolved_references=resolved_references,
        )


_PREPARATION_STAGES = frozenset(
    {
        ExecutionGraphStageType.CLONE_REPOSITORY,
        ExecutionGraphStageType.DOWNLOAD_DATASET,
        ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS,
        ExecutionGraphStageType.GENERATE_CONFIG,
    }
)

_EXPECTED_OUTPUTS = {
    ExecutionGraphStageType.CLONE_REPOSITORY: "repository",
    ExecutionGraphStageType.PREPARE_ENVIRONMENT: "environment",
    ExecutionGraphStageType.DOWNLOAD_DATASET: "dataset",
    ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS: "checkpoint",
    ExecutionGraphStageType.GENERATE_CONFIG: "configuration",
    ExecutionGraphStageType.TRAINING: "training_output",
    ExecutionGraphStageType.EVALUATION: "evaluation_output",
    ExecutionGraphStageType.COMPARISON: "report",
}


def _preparation_request(command: tuple[str, ...]) -> PreparationRequest | None:
    if "execution.preparation.command" not in command or "--request-json" not in command:
        return None
    index = command.index("--request-json")
    if index + 1 >= len(command):
        return None
    try:
        return PreparationRequest.model_validate_json(command[index + 1])
    except ValueError:
        return None


def _ancestor_ids(graph: ExecutionGraph, node_id: str) -> set[str]:
    by_id = {node.node_id: node for node in graph.nodes}
    ancestors: set[str] = set()
    pending = list(by_id[node_id].depends_on)
    while pending:
        current = pending.pop()
        if current in ancestors:
            continue
        ancestors.add(current)
        pending.extend(by_id[current].depends_on)
    return ancestors
