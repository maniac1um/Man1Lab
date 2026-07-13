"""Application wiring for Runtime-owned execution persistence."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.backends.local_executor import LocalExecutor
from execution.engine import ExecutionEngine
from execution.input_resolver.in_memory import InMemoryInputResolver
from execution.ports.artifacts import ArtifactTrackerPort
from execution.ports.executor import ExecutorPort
from execution.ports.persistence import ExecutionPersistencePort
from execution.ports.reconciliation import ReconciliationPort
from execution.reconciliation.in_memory import InMemoryReconciliationPort
from runtime.context import RuntimeContext
from runtime.execution_store import ExecutionStoreFactory, FileExecutionStore


def workspace_execution_store(workspace_root: Path) -> FileExecutionStore:
    """Construct a workspace-scoped execution store."""
    return ExecutionStoreFactory(workspace_root).store()


def bind_workspace_execution_store(context: RuntimeContext, workspace_root: Path) -> FileExecutionStore:
    """Attach a workspace-scoped store factory to runtime context."""
    factory = ExecutionStoreFactory(workspace_root)
    context.bind_execution_store(factory)
    return factory.store()


def build_attempt_logs_dir_resolver(store: FileExecutionStore) -> Callable[[str, str], str]:
    """Build a scheduler resolver for runtime-owned attempt log directories."""

    def resolve(run_id: str, attempt_id: str) -> str:
        return store.attempt_logs_dir(run_id, attempt_id).as_posix()

    return resolve


def logs_resolver_from_persistence(
    persistence: ExecutionPersistencePort,
) -> Callable[[str, str], str] | None:
    """Derive an attempt log resolver when the store exposes layout helpers."""
    if hasattr(persistence, "attempt_logs_dir"):
        store = persistence

        def resolve(run_id: str, attempt_id: str) -> str:
            return store.attempt_logs_dir(run_id, attempt_id).as_posix()  # type: ignore[union-attr]

        return resolve
    return None


def create_local_executor(
    workspace_root: Path,
    *,
    default_timeout_seconds: float | None = None,
) -> LocalExecutor:
    """Compose a local executor without backend-owned persistence paths."""
    return LocalExecutor(
        default_working_directory=workspace_root,
        default_timeout_seconds=default_timeout_seconds,
    )


def create_durable_engine(
    *,
    executor: ExecutorPort,
    persistence: ExecutionPersistencePort,
    artifact_tracker: ArtifactTrackerPort | None = None,
    input_resolver: InMemoryInputResolver | None = None,
    reconciliation: ReconciliationPort | None = None,
    logs_dir_resolver: Callable[[str, str], str] | None = None,
) -> ExecutionEngine:
    """Compose an execution engine with injected persistence and executor ports."""
    tracker = artifact_tracker or InMemoryArtifactTracker()
    resolved_logs = logs_dir_resolver or logs_resolver_from_persistence(persistence)
    return ExecutionEngine(
        executor=executor,
        artifact_tracker=tracker,
        input_resolver=input_resolver or InMemoryInputResolver(tracker),
        reconciliation=reconciliation or InMemoryReconciliationPort(),
        persistence=persistence,
        attempt_logs_dir_resolver=resolved_logs,
    )


def create_runtime_durable_engine(
    context: RuntimeContext,
    *,
    executor: ExecutorPort,
    artifact_tracker: ArtifactTrackerPort | None = None,
    input_resolver: InMemoryInputResolver | None = None,
    reconciliation: ReconciliationPort | None = None,
    logs_dir_resolver: Callable[[str, str], str] | None = None,
) -> ExecutionEngine:
    """Compose an engine using the Runtime-provided execution store."""
    store = context.execution_store()
    resolved_logs = logs_dir_resolver or build_attempt_logs_dir_resolver(store)
    return create_durable_engine(
        executor=executor,
        persistence=store,
        artifact_tracker=artifact_tracker,
        input_resolver=input_resolver,
        reconciliation=reconciliation,
        logs_dir_resolver=resolved_logs,
    )


def create_runtime_durable_local_engine(
    context: RuntimeContext,
    workspace_root: Path,
    *,
    artifact_tracker: ArtifactTrackerPort | None = None,
    input_resolver: InMemoryInputResolver | None = None,
    reconciliation: ReconciliationPort | None = None,
    default_timeout_seconds: float | None = None,
) -> ExecutionEngine:
    """Compose a durable engine with Runtime store and a local subprocess backend."""
    store = bind_workspace_execution_store(context, workspace_root)
    tracker = artifact_tracker or InMemoryArtifactTracker(
        workspace_root=workspace_root.as_posix(),
    )
    return create_durable_engine(
        executor=create_local_executor(
            workspace_root,
            default_timeout_seconds=default_timeout_seconds,
        ),
        persistence=store,
        artifact_tracker=tracker,
        input_resolver=input_resolver,
        reconciliation=reconciliation,
        logs_dir_resolver=build_attempt_logs_dir_resolver(store),
    )
