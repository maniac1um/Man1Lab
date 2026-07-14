"""Deterministic execution graph generation from planning outputs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
from models.execution_strategy import ExecutionStrategy, StrategyPosture
from models.research_resource_discovery import NeedCategory, ResearchAssetType, ResearchResourceDiscovery


def build_execution_graph(
    discovery: ResearchResourceDiscovery,
    strategy: ExecutionStrategy,
) -> ExecutionGraph:
    """Produce an execution-oriented dependency graph (planning only, not execution)."""
    now = datetime.now(UTC)
    nodes: list[ExecutionGraphNode] = []
    posture = strategy.strategy.primary_posture

    repo_binding = _binding_for_role(strategy, "primary_repository")
    dataset_binding = _binding_for_role(strategy, "dataset")
    checkpoint_binding = _binding_for_role(strategy, "checkpoint")
    config_binding = _binding_for_role(strategy, "configuration")

    repo_asset_id = repo_binding.candidate_id if repo_binding else ""
    dataset_asset_id = dataset_binding.candidate_id if dataset_binding else ""
    checkpoint_asset_id = checkpoint_binding.candidate_id if checkpoint_binding else ""

    last_node_id: str | None = None

    if posture != StrategyPosture.GREENFIELD and repo_binding is not None:
        clone_id = "node-clone-repository"
        nodes.append(
            ExecutionGraphNode(
                node_id=clone_id,
                stage_type=ExecutionGraphStageType.CLONE_REPOSITORY,
                label="Clone Repository",
                binding_ids=[repo_binding.binding_id],
                asset_ids=[repo_asset_id] if repo_asset_id else [],
                rationale="Primary repository binding requires workspace clone.",
            )
        )
        last_node_id = clone_id

    env_id = "node-prepare-environment"
    nodes.append(
        ExecutionGraphNode(
            node_id=env_id,
            stage_type=ExecutionGraphStageType.PREPARE_ENVIRONMENT,
            label="Prepare Environment",
            depends_on=[last_node_id] if last_node_id else [],
            binding_ids=_requirement_binding_ids(discovery),
            asset_ids=_asset_ids_by_type(discovery, ResearchAssetType.REQUIREMENTS, ResearchAssetType.ENVIRONMENT),
            rationale="Install dependencies and prepare runtime environment.",
        )
    )
    last_node_id = env_id

    if dataset_binding or _has_need(discovery, NeedCategory.DATASET):
        dataset_id = "node-download-dataset"
        nodes.append(
            ExecutionGraphNode(
                node_id=dataset_id,
                stage_type=ExecutionGraphStageType.DOWNLOAD_DATASET,
                label="Download Dataset",
                depends_on=[last_node_id],
                binding_ids=[dataset_binding.binding_id] if dataset_binding else [],
                asset_ids=[dataset_asset_id] if dataset_asset_id else _asset_ids_by_type(
                    discovery, ResearchAssetType.DATASET
                ),
                rationale="Stage dataset assets required for reproduction scope.",
            )
        )
        last_node_id = dataset_id

    if checkpoint_binding or strategy.strategy.primary_posture == StrategyPosture.HYBRID:
        checkpoint_id = "node-download-checkpoints"
        nodes.append(
            ExecutionGraphNode(
                node_id=checkpoint_id,
                stage_type=ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS,
                label="Download Checkpoints",
                depends_on=[last_node_id],
                binding_ids=[checkpoint_binding.binding_id] if checkpoint_binding else [],
                asset_ids=[checkpoint_asset_id]
                if checkpoint_asset_id
                else _asset_ids_by_type(discovery, ResearchAssetType.CHECKPOINT_WEIGHTS),
                rationale="Fetch pretrained weights when hybrid or checkpoint binding exists.",
            )
        )
        last_node_id = checkpoint_id

    if config_binding or strategy.generation_plan.generation_scope.value != "none":
        config_id = "node-generate-config"
        nodes.append(
            ExecutionGraphNode(
                node_id=config_id,
                stage_type=ExecutionGraphStageType.GENERATE_CONFIG,
                label="Generate Config",
                depends_on=[last_node_id],
                binding_ids=[config_binding.binding_id] if config_binding else [],
                asset_ids=_asset_ids_by_type(discovery, ResearchAssetType.CONFIGURATION),
                rationale="Materialize configuration for training or evaluation.",
            )
        )
        last_node_id = config_id

    if posture != StrategyPosture.GREENFIELD or not strategy.generation_plan.generation_required:
        training_id = "node-training"
        nodes.append(
            ExecutionGraphNode(
                node_id=training_id,
                stage_type=ExecutionGraphStageType.TRAINING,
                label="Training",
                depends_on=[last_node_id],
                binding_ids=[item.binding_id for item in strategy.resource_bindings.bindings],
                asset_ids=[item.asset_id for item in discovery.research_assets.assets if item.selected_primary],
                rationale="Execute training stage when reuse or hybrid posture applies.",
            )
        )
        last_node_id = training_id

    eval_id = "node-evaluation"
    nodes.append(
        ExecutionGraphNode(
            node_id=eval_id,
            stage_type=ExecutionGraphStageType.EVALUATION,
            label="Evaluation",
            depends_on=[last_node_id],
            asset_ids=_asset_ids_by_type(
                discovery,
                ResearchAssetType.BENCHMARK,
                ResearchAssetType.EVALUATION_SCRIPT,
            ),
            rationale="Run evaluation harness against reproduced artifacts.",
        )
    )

    nodes.append(
        ExecutionGraphNode(
            node_id="node-comparison",
            stage_type=ExecutionGraphStageType.COMPARISON,
            label="Comparison",
            depends_on=[eval_id],
            rationale="Compare reproduced metrics against paper-reported baselines.",
        )
    )

    return ExecutionGraph(
        graph_id=f"graph-{uuid.uuid4()}",
        created_at=now,
        strategy_id=strategy.metadata.strategy_id,
        nodes=nodes,
    )


def _binding_for_role(strategy: ExecutionStrategy, role_suffix: str):
    for binding in strategy.resource_bindings.bindings:
        if binding.role.value.endswith(role_suffix) or binding.role.value == role_suffix:
            return binding
    for binding in strategy.resource_bindings.bindings:
        if role_suffix in binding.role.value:
            return binding
    return None


def _has_need(discovery: ResearchResourceDiscovery, category: NeedCategory) -> bool:
    for selection in discovery.selection.selections:
        if selection.resource_need.need_category == category:
            return True
    return False


def _asset_ids_by_type(discovery: ResearchResourceDiscovery, *asset_types: ResearchAssetType) -> list[str]:
    allowed = {item.value for item in asset_types}
    return [
        asset.asset_id
        for asset in discovery.research_assets.assets
        if asset.asset_type.value in allowed
    ]


def _requirement_binding_ids(discovery: ResearchResourceDiscovery) -> list[str]:
    del discovery
    return []
