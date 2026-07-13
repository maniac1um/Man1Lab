"""Shared fixtures for materialization tests."""

from __future__ import annotations

from datetime import UTC, datetime

from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
from models.execution_strategy import (
    AnalysisReference,
    BindingRole,
    DiscoveryReference,
    ExecutionStrategy,
    InputReferences,
    PlanningStatus,
    ResourceBinding,
    ResourceBindings,
    Strategy,
    StrategyMetadata,
    StrategyPosture,
)
from models.research_resource_discovery import DiscoveryStatus


def strategy_with_primary_repo(strategy_id: str = "strategy-1") -> ExecutionStrategy:
    return ExecutionStrategy(
        metadata=StrategyMetadata(
            strategy_id=strategy_id,
            status=PlanningStatus.COMPLETE,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        input_references=InputReferences(
            analysis_reference=AnalysisReference(
                analysis_schema_version="1.0",
                paper_title="Test",
                analysis_content_hash="hash-1",
            ),
            discovery_reference=DiscoveryReference(
                discovery_schema_version="1.0",
                discovery_id="discovery-1",
                discovery_content_hash="discovery-hash",
                discovery_status=DiscoveryStatus.COMPLETE,
            ),
        ),
        strategy=Strategy(
            primary_posture=StrategyPosture.OFFICIAL_REPOSITORY,
            rationale="Reuse official repository.",
        ),
        resource_bindings=ResourceBindings(
            bindings=[
                ResourceBinding(
                    binding_id="binding-primary-repository",
                    candidate_id="candidate-repo-1",
                    role=BindingRole.PRIMARY_REPOSITORY,
                )
            ],
            anchor_binding_id="binding-primary-repository",
        ),
    )


def materializable_graph() -> ExecutionGraph:
    return ExecutionGraph(
        graph_id="graph-materializable",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        strategy_id="strategy-1",
        nodes=[
            ExecutionGraphNode(
                node_id="node-prepare-environment",
                stage_type=ExecutionGraphStageType.PREPARE_ENVIRONMENT,
                label="Prepare Environment",
                binding_ids=["binding-primary-repository"],
            ),
            ExecutionGraphNode(
                node_id="node-training",
                stage_type=ExecutionGraphStageType.TRAINING,
                label="Training",
                depends_on=["node-prepare-environment"],
                binding_ids=["binding-primary-repository"],
            ),
            ExecutionGraphNode(
                node_id="node-evaluation",
                stage_type=ExecutionGraphStageType.EVALUATION,
                label="Evaluation",
                depends_on=["node-training"],
                binding_ids=["binding-primary-repository"],
            ),
            ExecutionGraphNode(
                node_id="node-comparison",
                stage_type=ExecutionGraphStageType.COMPARISON,
                label="Comparison",
                depends_on=["node-evaluation"],
                binding_ids=["binding-primary-repository"],
            ),
        ],
    )
