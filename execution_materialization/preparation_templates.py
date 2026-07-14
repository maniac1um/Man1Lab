"""Versioned preparation templates for ordinary Planning graph stages."""

from __future__ import annotations

import sys
from pathlib import Path

from models.executable_task_spec import ExecutableTaskSpec
from models.execution_preparation import PreparationOperation, PreparationRequest
from models.execution_evidence import (
    CheckpointExecutionEvidence,
    ConfigurationExecutionEvidence,
    ConfigurationMode,
    DatasetExecutionEvidence,
    ExecutionEvidenceBundle,
    PreparationSourceKind,
    RepositoryExecutionEvidence,
)
from models.execution_graph import ExecutionGraphNode, ExecutionGraphStageType
from models.execution_materialization import MaterializationIssue, MaterializationIssueSeverity


PREPARATION_STAGES = frozenset(
    {
        ExecutionGraphStageType.CLONE_REPOSITORY,
        ExecutionGraphStageType.DOWNLOAD_DATASET,
        ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS,
        ExecutionGraphStageType.GENERATE_CONFIG,
    }
)


def build_preparation_spec(
    node: ExecutionGraphNode,
    *,
    bundle: ExecutionEvidenceBundle,
    bindings_by_id: dict[str, str],
) -> ExecutableTaskSpec | MaterializationIssue:
    candidate_ids = _candidate_ids(node, bindings_by_id)
    receipt = f".man1lab/preparation/{node.node_id}/{_receipt_name(node.stage_type)}"

    if node.stage_type is ExecutionGraphStageType.CLONE_REPOSITORY:
        descriptor = _select(bundle.repositories, candidate_ids)
        if descriptor is None:
            return _missing(node, "repository execution evidence")
        if descriptor.auth_reference:
            return _unsupported(node, "authenticated repository preparation is not supported yet")
        if descriptor.source_kind is PreparationSourceKind.GIT and not descriptor.revision:
            return _missing(node, "immutable repository revision")
        request = PreparationRequest(
            operation=PreparationOperation.REPOSITORY,
            source_kind=descriptor.source_kind.value,
            source_uri=descriptor.source_uri,
            target_path=descriptor.target_path,
            receipt_path=receipt,
            revision=descriptor.revision,
            required_paths=_required_repository_paths(descriptor),
        )
        return _spec(node, request, receipt, "repository", descriptor.candidate_id)

    if node.stage_type is ExecutionGraphStageType.DOWNLOAD_DATASET:
        descriptor = _select(bundle.datasets, candidate_ids)
        if descriptor is None:
            return _missing(node, "dataset execution evidence")
        return _asset_spec(node, descriptor, receipt, PreparationOperation.DATASET, "dataset")

    if node.stage_type is ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS:
        descriptor = _select(bundle.checkpoints, candidate_ids)
        if descriptor is None:
            return _missing(node, "checkpoint execution evidence")
        return _asset_spec(node, descriptor, receipt, PreparationOperation.CHECKPOINT, "checkpoint")

    if node.stage_type is ExecutionGraphStageType.GENERATE_CONFIG:
        descriptor = _select(bundle.configurations, candidate_ids)
        if descriptor is None and len(bundle.configurations) == 1:
            descriptor = bundle.configurations[0]
        if descriptor is None:
            return _missing(node, "configuration execution evidence")
        source_kind = (
            PreparationSourceKind.DETERMINISTIC_RENDER.value
            if descriptor.mode is ConfigurationMode.DETERMINISTIC_RENDER
            else PreparationSourceKind.WORKSPACE.value
        )
        request = PreparationRequest(
            operation=PreparationOperation.CONFIGURATION,
            source_kind=source_kind,
            source_path=descriptor.source_path,
            target_path=descriptor.target_path,
            receipt_path=receipt,
            configuration_format=descriptor.format,
            configuration_values=descriptor.values,
        )
        return _spec(node, request, receipt, "configuration", descriptor.candidate_id)

    return _unsupported(node, "not a preparation stage")


def primary_repository(bundle: ExecutionEvidenceBundle, candidate_id: str | None) -> RepositoryExecutionEvidence | None:
    if candidate_id:
        for descriptor in bundle.repositories:
            if descriptor.candidate_id == candidate_id:
                return descriptor
    return bundle.repositories[0] if len(bundle.repositories) == 1 else None


def _asset_spec(
    node: ExecutionGraphNode,
    descriptor: DatasetExecutionEvidence | CheckpointExecutionEvidence,
    receipt: str,
    operation: PreparationOperation,
    logical_name: str,
) -> ExecutableTaskSpec | MaterializationIssue:
    if descriptor.auth_reference:
        return _unsupported(node, f"authenticated {logical_name} preparation is not supported yet")
    if descriptor.source_kind is PreparationSourceKind.HTTPS and not descriptor.checksum_sha256:
        return _missing(node, f"checksum_sha256 for remote {logical_name}")
    request = PreparationRequest(
        operation=operation,
        source_kind=descriptor.source_kind.value,
        source_uri=descriptor.source_uri,
        target_path=descriptor.target_path,
        receipt_path=receipt,
        revision=descriptor.revision,
        checksum_sha256=descriptor.checksum_sha256,
        archive_format=descriptor.archive_format,
    )
    return _spec(node, request, receipt, logical_name, descriptor.candidate_id)


def _spec(
    node: ExecutionGraphNode,
    request: PreparationRequest,
    receipt: str,
    logical_name: str,
    candidate_id: str,
) -> ExecutableTaskSpec:
    return ExecutableTaskSpec(
        command=(
            sys.executable,
            "-m",
            "execution.preparation.command",
            "--request-json",
            request.model_dump_json(),
        ),
        working_directory=".",
        environment_variables={
            "MAN1LAB_RUN_MODE": "reproduction",
            "PYTHONPATH": Path(__file__).resolve().parents[1].as_posix(),
        },
        timeout_seconds=3600.0,
        artifact_paths={logical_name: receipt},
        template_id=f"local/prepare_{logical_name}",
        template_version="1.0",
        source_binding_ids=tuple(node.binding_ids),
        source_asset_ids=tuple(node.asset_ids),
        provenance=f"execution-evidence:{candidate_id}",
    )


def _candidate_ids(node: ExecutionGraphNode, bindings_by_id: dict[str, str]) -> tuple[str, ...]:
    values = [bindings_by_id[binding] for binding in node.binding_ids if binding in bindings_by_id]
    values.extend(node.asset_ids)
    return tuple(dict.fromkeys(values))


def _select(items, candidate_ids: tuple[str, ...]):
    matches = [item for item in items if item.candidate_id in candidate_ids]
    return matches[0] if len(matches) == 1 else None


def _required_repository_paths(descriptor: RepositoryExecutionEvidence) -> tuple[str, ...]:
    values = [
        descriptor.entry_script,
        descriptor.eval_script,
        descriptor.comparison_script,
        descriptor.requirements_file,
        descriptor.config_path,
        *descriptor.manifest_paths,
    ]
    return tuple(dict.fromkeys(value for value in values if value))


def _receipt_name(stage_type: ExecutionGraphStageType) -> str:
    return {
        ExecutionGraphStageType.CLONE_REPOSITORY: "repository_receipt.json",
        ExecutionGraphStageType.DOWNLOAD_DATASET: "dataset_receipt.json",
        ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS: "checkpoint_receipt.json",
        ExecutionGraphStageType.GENERATE_CONFIG: "configuration_receipt.json",
    }[stage_type]


def _missing(node: ExecutionGraphNode, what: str) -> MaterializationIssue:
    return MaterializationIssue(
        code="missing_execution_evidence",
        message=f"missing {what}",
        severity=MaterializationIssueSeverity.ERROR,
        node_id=node.node_id,
        stage_type=node.stage_type.value,
    )


def _unsupported(node: ExecutionGraphNode, message: str) -> MaterializationIssue:
    return MaterializationIssue(
        code="unsupported_preparation",
        message=message,
        severity=MaterializationIssueSeverity.ERROR,
        node_id=node.node_id,
        stage_type=node.stage_type.value,
    )
