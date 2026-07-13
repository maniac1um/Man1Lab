"""Application wiring for execution materialization."""

from __future__ import annotations

from pathlib import Path

from execution_materialization.materializer import ExecutionMaterializer
from execution_materialization.ports import MaterializationContext
from execution_materialization.templates import TaskTemplateRegistry
from execution_materialization.validation import ExecutionReadinessValidator
from models.execution_graph import ExecutionGraph
from models.execution_materialization import ExecutionMaterialization
from models.execution_strategy import ExecutionStrategy
from models.research_resource_discovery import ResearchResourceDiscovery
from runtime.session.materialization_artifacts import MaterializationArtifactStore


def create_materialization_context(workspace_root: Path, *, backend_kind: str = "local") -> MaterializationContext:
    return MaterializationContext(
        workspace_root=workspace_root.as_posix(),
        backend_kind=backend_kind,
    )


def create_execution_materializer() -> ExecutionMaterializer:
    return ExecutionMaterializer(
        template_registry=TaskTemplateRegistry(),
        readiness_validator=ExecutionReadinessValidator(),
    )


def materialize_execution_graph(
    *,
    strategy: ExecutionStrategy,
    discovery: ResearchResourceDiscovery,
    graph: ExecutionGraph,
    workspace_root: Path,
    materializer: ExecutionMaterializer | None = None,
) -> ExecutionMaterialization:
    """Materialize an abstract planning graph for the given workspace."""
    resolved = materializer or create_execution_materializer()
    context = create_materialization_context(workspace_root)
    return resolved.materialize(strategy, discovery, graph, context)


def persist_materialization(workspace_root: Path, materialization: ExecutionMaterialization) -> None:
    MaterializationArtifactStore(workspace_root).save(materialization)
