"""Shared fixtures for execution engine tests."""

from __future__ import annotations

from datetime import UTC, datetime

from models.execution_graph import (
    ExecutionGraph,
    ExecutionGraphNode,
    ExecutionGraphStageType,
)


def linear_graph() -> ExecutionGraph:
    return ExecutionGraph(
        graph_id="graph-linear",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        strategy_id="strategy-1",
        nodes=[
            ExecutionGraphNode(
                node_id="node-prepare-environment",
                stage_type=ExecutionGraphStageType.PREPARE_ENVIRONMENT,
                label="Prepare Environment",
            ),
            ExecutionGraphNode(
                node_id="node-training",
                stage_type=ExecutionGraphStageType.TRAINING,
                label="Training",
                depends_on=["node-prepare-environment"],
            ),
            ExecutionGraphNode(
                node_id="node-evaluation",
                stage_type=ExecutionGraphStageType.EVALUATION,
                label="Evaluation",
                depends_on=["node-training"],
            ),
        ],
    )


def branching_graph() -> ExecutionGraph:
    return ExecutionGraph(
        graph_id="graph-branch",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        strategy_id="strategy-branch",
        nodes=[
            ExecutionGraphNode(
                node_id="node-prepare-environment",
                stage_type=ExecutionGraphStageType.PREPARE_ENVIRONMENT,
                label="Prepare Environment",
            ),
            ExecutionGraphNode(
                node_id="node-download-dataset",
                stage_type=ExecutionGraphStageType.DOWNLOAD_DATASET,
                label="Download Dataset",
                depends_on=["node-prepare-environment"],
            ),
            ExecutionGraphNode(
                node_id="node-training",
                stage_type=ExecutionGraphStageType.TRAINING,
                label="Training",
                depends_on=["node-prepare-environment"],
            ),
            ExecutionGraphNode(
                node_id="node-evaluation",
                stage_type=ExecutionGraphStageType.EVALUATION,
                label="Evaluation",
                depends_on=["node-download-dataset", "node-training"],
            ),
        ],
    )


def full_stage_graph() -> ExecutionGraph:
    last: str | None = None
    nodes: list[ExecutionGraphNode] = []
    stages = [
        ("node-clone-repository", ExecutionGraphStageType.CLONE_REPOSITORY, "Clone Repository"),
        ("node-prepare-environment", ExecutionGraphStageType.PREPARE_ENVIRONMENT, "Prepare Environment"),
        ("node-download-dataset", ExecutionGraphStageType.DOWNLOAD_DATASET, "Download Dataset"),
        ("node-download-checkpoints", ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS, "Download Checkpoints"),
        ("node-generate-config", ExecutionGraphStageType.GENERATE_CONFIG, "Generate Config"),
        ("node-training", ExecutionGraphStageType.TRAINING, "Training"),
        ("node-evaluation", ExecutionGraphStageType.EVALUATION, "Evaluation"),
        ("node-comparison", ExecutionGraphStageType.COMPARISON, "Comparison"),
    ]
    for node_id, stage_type, label in stages:
        nodes.append(
            ExecutionGraphNode(
                node_id=node_id,
                stage_type=stage_type,
                label=label,
                depends_on=[last] if last else [],
                binding_ids=[f"binding-{node_id}"] if stage_type != ExecutionGraphStageType.COMPARISON else [],
                asset_ids=[f"asset-{node_id}"] if stage_type != ExecutionGraphStageType.COMPARISON else [],
                rationale=f"Rationale for {label}",
            )
        )
        last = node_id
    return ExecutionGraph(
        graph_id="graph-full",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        strategy_id="strategy-full",
        nodes=nodes,
    )
