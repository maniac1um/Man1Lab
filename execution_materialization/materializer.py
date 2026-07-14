"""Orchestrate node-by-node planning-to-execution materialization."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from execution_materialization.graph_builder import build_materialized_graph
from execution_materialization.ports import MaterializationContext, ResolvedReference
from execution_materialization.preparation_templates import (
    PREPARATION_STAGES,
    build_preparation_spec,
    primary_repository,
)
from execution_materialization.resolvers.workspace import (
    WorkspaceEntrypointResolver,
    WorkspaceEnvironmentLocationResolver,
    WorkspaceRepositoryLocationResolver,
)
from execution_materialization.templates import TaskTemplateRegistry, build_spec_from_template
from execution_materialization.validation import ExecutionReadinessValidator
from models.execution_evidence import (
    EvidenceAvailability,
    ExecutionEvidenceBundle,
    PreparationSourceKind,
    RepositoryExecutionEvidence,
)
from models.execution_graph import ExecutionGraph, ExecutionGraphStageType
from models.execution_materialization import (
    ExecutionMaterialization,
    MaterializationIssue,
    MaterializationIssueSeverity,
    MaterializationStatus,
    NodeMaterializationResult,
)
from models.execution_strategy import BindingRole, ExecutionStrategy
from models.research_resource_discovery import ResearchResourceDiscovery


class ExecutionMaterializer:
    """Deterministic, side-effect-free materialization orchestrator."""

    def __init__(
        self,
        *,
        template_registry: TaskTemplateRegistry | None = None,
        readiness_validator: ExecutionReadinessValidator | None = None,
    ) -> None:
        self._templates = template_registry or TaskTemplateRegistry()
        self._validator = readiness_validator or ExecutionReadinessValidator()

    def materialize(
        self,
        strategy: ExecutionStrategy,
        discovery: ResearchResourceDiscovery,
        graph: ExecutionGraph,
        context: MaterializationContext,
        evidence_bundle: ExecutionEvidenceBundle | None = None,
    ) -> ExecutionMaterialization:
        bindings_by_id = {
            binding.binding_id: binding.candidate_id for binding in strategy.resource_bindings.bindings
        }
        repo_resolver = WorkspaceRepositoryLocationResolver(context, discovery, bindings_by_id=bindings_by_id)
        env_resolver = WorkspaceEnvironmentLocationResolver(context, discovery, bindings_by_id=bindings_by_id)
        entry_resolver = WorkspaceEntrypointResolver(context, discovery, bindings_by_id=bindings_by_id)

        primary_repo_binding = next(
            (
                binding
                for binding in strategy.resource_bindings.bindings
                if binding.role is BindingRole.PRIMARY_REPOSITORY
            ),
            None,
        )
        primary_repo = None
        if primary_repo_binding is not None:
            primary_repo = repo_resolver.resolve_repository(
                primary_repo_binding.binding_id,
                primary_repo_binding.candidate_id,
            )
        primary_repo_descriptor = (
            primary_repository(
                evidence_bundle,
                primary_repo_binding.candidate_id if primary_repo_binding is not None else None,
            )
            if evidence_bundle is not None
            else None
        )
        repository_producer_id = next(
            (
                node.node_id
                for node in graph.nodes
                if node.stage_type is ExecutionGraphStageType.CLONE_REPOSITORY
            ),
            None,
        )
        if primary_repo_descriptor is not None:
            primary_repo = ResolvedReference(
                logical_name="repository",
                path=primary_repo_descriptor.target_path,
                source_kind="execution_evidence",
                source_id=primary_repo_descriptor.candidate_id,
                availability=(
                    EvidenceAvailability.WILL_BE_PRODUCED
                    if primary_repo_descriptor.source_kind is PreparationSourceKind.GIT
                    else EvidenceAvailability.PRESENT
                ),
                producer_node_id=repository_producer_id,
                producer_output="repository" if repository_producer_id else None,
            )

        resolved_references: dict[str, str] = {}
        node_specs: dict[str, object] = {}
        node_results: list[NodeMaterializationResult] = []
        errors: list[MaterializationIssue] = []

        for node in graph.nodes:
            binding_ids = tuple(node.binding_ids)
            asset_ids = tuple(node.asset_ids)
            resolution_binding_ids = binding_ids
            if (
                primary_repo_binding is not None
                and primary_repo_binding.binding_id not in resolution_binding_ids
            ):
                resolution_binding_ids = (*resolution_binding_ids, primary_repo_binding.binding_id)
            if node.stage_type in PREPARATION_STAGES and evidence_bundle is not None:
                built = build_preparation_spec(
                    node,
                    bundle=evidence_bundle,
                    bindings_by_id=bindings_by_id,
                )
                if isinstance(built, MaterializationIssue):
                    node_results.append(
                        NodeMaterializationResult(
                            node_id=node.node_id,
                            stage_type=node.stage_type.value,
                            status=(
                                MaterializationStatus.UNSUPPORTED
                                if built.code == "unsupported_preparation"
                                else MaterializationStatus.BLOCKED
                            ),
                            issues=(built,),
                        )
                    )
                    errors.append(built)
                else:
                    node_specs[node.node_id] = built
                    node_results.append(
                        NodeMaterializationResult(
                            node_id=node.node_id,
                            stage_type=node.stage_type.value,
                            status=MaterializationStatus.READY,
                            template_id=built.template_id,
                            template_version=built.template_version,
                        )
                    )
                continue
            template_resolution = self._templates.resolve(node.stage_type)
            if template_resolution.issue is not None:
                node_results.append(
                    NodeMaterializationResult(
                        node_id=node.node_id,
                        stage_type=node.stage_type.value,
                        status=MaterializationStatus.UNSUPPORTED,
                        issues=(template_resolution.issue,),
                    )
                )
                errors.append(template_resolution.issue)
                continue

            template = template_resolution.template
            assert template is not None

            if node.stage_type in {
                ExecutionGraphStageType.CLONE_REPOSITORY,
                ExecutionGraphStageType.DOWNLOAD_DATASET,
                ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS,
                ExecutionGraphStageType.GENERATE_CONFIG,
            }:
                issue = MaterializationIssue(
                    code="unsupported_stage",
                    message=f"stage {node.stage_type.value} requires effects outside materialization scope",
                    severity=MaterializationIssueSeverity.ERROR,
                    node_id=node.node_id,
                    stage_type=node.stage_type.value,
                    template_id=template.template_id,
                )
                node_results.append(
                    NodeMaterializationResult(
                        node_id=node.node_id,
                        stage_type=node.stage_type.value,
                        status=MaterializationStatus.UNSUPPORTED,
                        issues=(issue,),
                    )
                )
                errors.append(issue)
                continue

            evidence = self._collect_evidence(
                node.stage_type,
                binding_ids=resolution_binding_ids,
                asset_ids=asset_ids,
                primary_repo=primary_repo,
                repo_resolver=repo_resolver,
                env_resolver=env_resolver,
                entry_resolver=entry_resolver,
                primary_repo_descriptor=primary_repo_descriptor,
                evidence_bundle=evidence_bundle,
                repository_producer_id=repository_producer_id,
            )
            for key, ref in evidence.items():
                resolved_references[f"{node.node_id}:{key}"] = ref.path

            built = build_spec_from_template(
                template=template,
                stage_type=node.stage_type,
                working_directory="",
                evidence=evidence,
                binding_ids=binding_ids,
                asset_ids=asset_ids,
                environment_variables={"MAN1LAB_RUN_MODE": "reproduction"},
            )
            if isinstance(built, MaterializationIssue):
                node_results.append(
                    NodeMaterializationResult(
                        node_id=node.node_id,
                        stage_type=node.stage_type.value,
                        status=MaterializationStatus.BLOCKED,
                        template_id=template.template_id,
                        template_version=template.template_version,
                        issues=(built,),
                    )
                )
                errors.append(built)
                continue

            node_specs[node.node_id] = built
            node_results.append(
                NodeMaterializationResult(
                    node_id=node.node_id,
                    stage_type=node.stage_type.value,
                    status=MaterializationStatus.READY,
                    template_id=template.template_id,
                    template_version=template.template_version,
                )
            )

        materialization_id = _materialization_id(strategy.metadata.strategy_id, graph.graph_id, context)
        materialized_graph = build_materialized_graph(
            graph,
            materialization_id=materialization_id,
            node_specs=node_specs,  # type: ignore[arg-type]
        )
        report = self._validator.validate(
            materialized_graph,
            node_results=tuple(node_results),
            resolved_references=resolved_references,
        )
        if errors and report.status is MaterializationStatus.READY:
            report = report.model_copy(
                update={
                    "status": MaterializationStatus.BLOCKED,
                    "errors": tuple([*report.errors, *errors]),
                }
            )

        return ExecutionMaterialization(
            materialization_id=materialization_id,
            strategy_id=strategy.metadata.strategy_id,
            graph_id=graph.graph_id,
            discovery_id=discovery.metadata.discovery_id,
            analysis_id=discovery.analysis_reference.analysis_content_hash,
            evidence_bundle_id=evidence_bundle.bundle_id if evidence_bundle is not None else None,
            backend_kind=context.backend_kind,
            materialized_graph=materialized_graph,
            report=report,
            created_at=datetime.now(UTC),
        )

    def _collect_evidence(
        self,
        stage_type: ExecutionGraphStageType,
        *,
        binding_ids: tuple[str, ...],
        asset_ids: tuple[str, ...],
        primary_repo,
        repo_resolver: WorkspaceRepositoryLocationResolver,
        env_resolver: WorkspaceEnvironmentLocationResolver,
        entry_resolver: WorkspaceEntrypointResolver,
        primary_repo_descriptor: RepositoryExecutionEvidence | None,
        evidence_bundle: ExecutionEvidenceBundle | None,
        repository_producer_id: str | None,
    ) -> dict[str, object]:
        evidence: dict[str, object] = {}
        if primary_repo is not None:
            evidence["prepared_repo_path"] = primary_repo
        if primary_repo_descriptor is not None:
            descriptor_paths = {
                "entry_script": primary_repo_descriptor.entry_script,
                "eval_script": primary_repo_descriptor.eval_script,
                "comparison_script": primary_repo_descriptor.comparison_script,
                "requirements_file": primary_repo_descriptor.requirements_file,
                "config_path": primary_repo_descriptor.config_path,
                "output_path": primary_repo_descriptor.output_path,
            }
            for logical_name, path in descriptor_paths.items():
                if path:
                    evidence[logical_name] = ResolvedReference(
                        logical_name=logical_name,
                        path=path,
                        source_kind="execution_evidence",
                        source_id=primary_repo_descriptor.candidate_id,
                        availability=(
                            EvidenceAvailability.WILL_BE_PRODUCED
                            if primary_repo_descriptor.source_kind is PreparationSourceKind.GIT
                            else EvidenceAvailability.PRESENT
                        ),
                        producer_node_id=repository_producer_id,
                        producer_output="repository" if repository_producer_id else None,
                    )
        if evidence_bundle is not None and evidence_bundle.configurations:
            configuration = evidence_bundle.configurations[0]
            evidence["config_path"] = ResolvedReference(
                logical_name="config_path",
                path=configuration.target_path,
                source_kind="execution_evidence",
                source_id=configuration.candidate_id,
            )

        for binding_id in binding_ids:
            resolved = repo_resolver.resolve_repository(binding_id)
            if resolved is not None:
                evidence["prepared_repo_path"] = resolved

        if stage_type is ExecutionGraphStageType.PREPARE_ENVIRONMENT:
            env_ref = env_resolver.resolve_environment(binding_ids, asset_ids)
            if env_ref is not None and "requirements_file" not in evidence:
                evidence["requirements_file"] = env_ref

        if stage_type in {ExecutionGraphStageType.TRAINING, ExecutionGraphStageType.EVALUATION}:
            entry = entry_resolver.resolve_entrypoint(
                binding_ids,
                asset_ids,
                stage_kind=stage_type.value,
            )
            key = "eval_script" if stage_type is ExecutionGraphStageType.EVALUATION else "entry_script"
            if entry is not None and key not in evidence:
                evidence[key] = entry
            config = entry_resolver.resolve_config(binding_ids, asset_ids)
            if config is not None and "config_path" not in evidence:
                evidence["config_path"] = config
            output = entry_resolver.resolve_output(binding_ids, asset_ids)
            if output is not None and "output_path" not in evidence:
                evidence["output_path"] = output

        if stage_type is ExecutionGraphStageType.COMPARISON:
            entry = entry_resolver.resolve_entrypoint(
                binding_ids,
                asset_ids,
                stage_kind=stage_type.value,
            )
            if entry is not None and "comparison_script" not in evidence:
                evidence["comparison_script"] = entry
            output = entry_resolver.resolve_output(binding_ids, asset_ids)
            if output is not None and "output_path" not in evidence:
                evidence["output_path"] = output

        return evidence  # type: ignore[return-value]


def _materialization_id(strategy_id: str, graph_id: str, context: MaterializationContext) -> str:
    digest = hashlib.sha256(
        f"{strategy_id}:{graph_id}:{context.workspace_root}:{context.backend_kind}".encode("utf-8")
    ).hexdigest()[:24]
    return f"mat-{digest}"
