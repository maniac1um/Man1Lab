"""Workspace-scoped execution store factory."""

from __future__ import annotations

from pathlib import Path

from execution.ports.persistence import ExecutionPersistencePort
from runtime.execution_store.file_store import FileExecutionStore


class ExecutionStoreFactory:
    """Creates workspace-scoped FileExecutionStore instances."""

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root
        self._store: FileExecutionStore | None = None

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def for_workspace(self, workspace_root: Path) -> ExecutionStoreFactory:
        """Return a factory bound to a different workspace root."""
        return ExecutionStoreFactory(workspace_root)

    def store(self) -> FileExecutionStore:
        if self._store is None:
            self._store = FileExecutionStore(self._workspace_root / "execution" / "runs")
        return self._store

    def persistence_port(self) -> ExecutionPersistencePort:
        return self.store()

    def release_all_writers(self) -> None:
        if self._store is not None:
            self._store.release_all_writers()
