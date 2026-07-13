"""Readiness validation for materialized execution graphs."""

from __future__ import annotations

from models.execution_graph import ExecutionGraph, ExecutionGraphStageType
from models.execution_materialization import (
    MaterializationIssue,
    MaterializationIssueSeverity,
    MaterializationReport,
    MaterializationStatus,
    NodeMaterializationResult,
)


_UNSUPPORTED_STAGES = frozenset(
    {
        ExecutionGraphStageType.CLONE_REPOSITORY,
        ExecutionGraphStageType.DOWNLOAD_DATASET,
        ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS,
        ExecutionGraphStageType.GENERATE_CONFIG,
    }
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

        for node in graph.nodes:
            if node.stage_type in _UNSUPPORTED_STAGES:
                errors.append(
                    MaterializationIssue(
                        code="unsupported_stage",
                        message=f"stage {node.stage_type.value} is not supported in v1.3 materialization",
                        severity=MaterializationIssueSeverity.ERROR,
                        node_id=node.node_id,
                        stage_type=node.stage_type.value,
                    )
                )
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
