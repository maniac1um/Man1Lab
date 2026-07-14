"""Experiment tracker protocol — business code depends on this, not MLflow."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ExperimentTracker(Protocol):
    """Thin tracking facade for experiments, runs, params, metrics, artifacts, tags."""

    @contextmanager
    def start_run(
        self,
        *,
        run_name: str,
        experiment_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Iterator[ExperimentTracker]:
        """Start a top-level reproduction run (one paper = one run)."""
        ...

    @contextmanager
    def start_nested_run(
        self,
        name: str,
        tags: dict[str, str] | None = None,
    ) -> Iterator[ExperimentTracker]:
        """Start a nested run (e.g. pipeline stage within a reproduction)."""
        ...

    def log_param(self, key: str, value: str | int | float | bool) -> None: ...

    def log_metric(self, key: str, value: float, step: int | None = None) -> None: ...

    def log_artifact(self, local_path: str | Path) -> None: ...

    def set_tag(self, key: str, value: str) -> None: ...
