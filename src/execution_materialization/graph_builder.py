"""Copy planning graphs and attach typed execution specifications."""

from __future__ import annotations

from models.execution_graph import (
    MATERIALIZATION_SCHEMA_VERSION,
    ExecutionGraph,
    ExecutionGraphNode,
)
from models.execution_materialization import ExecutableTaskSpec


def build_materialized_graph(
    source: ExecutionGraph,
    *,
    materialization_id: str,
    node_specs: dict[str, ExecutableTaskSpec],
) -> ExecutionGraph:
    """Produce a new graph with identical topology and enriched node specs."""
    _assert_topology_unchanged(source, node_specs)
    nodes: list[ExecutionGraphNode] = []
    for node in source.nodes:
        spec = node_specs.get(node.node_id)
        nodes.append(
            ExecutionGraphNode(
                node_id=node.node_id,
                stage_type=node.stage_type,
                label=node.label,
                depends_on=list(node.depends_on),
                binding_ids=list(node.binding_ids),
                asset_ids=list(node.asset_ids),
                rationale=node.rationale,
                execution_spec=spec,
            )
        )
    return ExecutionGraph(
        graph_id=source.graph_id,
        created_at=source.created_at,
        strategy_id=source.strategy_id,
        nodes=nodes,
        schema_version=source.schema_version,
        materialization_id=materialization_id,
        materialization_schema_version=MATERIALIZATION_SCHEMA_VERSION,
    )


def _assert_topology_unchanged(source: ExecutionGraph, node_specs: dict[str, ExecutableTaskSpec]) -> None:
    source_ids = {node.node_id for node in source.nodes}
    if set(node_specs) - source_ids:
        unknown = sorted(set(node_specs) - source_ids)
        raise ValueError(f"materialization attempted to add unknown nodes: {', '.join(unknown)}")
