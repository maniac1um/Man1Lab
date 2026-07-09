"""Runtime-owned hooks to persist decision artifacts after stage completion."""

from __future__ import annotations

import importlib

from runtime.session.workspace_store import WorkspaceArtifactStore


def persist_discovery_decision_artifacts(store: WorkspaceArtifactStore, discovery) -> None:
    builder = importlib.import_module("discovery.decision_trace")
    store.save_decision_trace(builder.build_discovery_decision_trace(discovery))


def persist_planning_decision_artifacts(
    store: WorkspaceArtifactStore,
    discovery,
    strategy,
) -> None:
    trace_builder = importlib.import_module("execution_planning.decision_trace")
    graph_builder = importlib.import_module("execution_planning.execution_graph")
    store.save_decision_trace(trace_builder.build_planning_decision_trace(discovery, strategy))
    store.save_execution_graph(graph_builder.build_execution_graph(discovery, strategy))
