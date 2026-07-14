"""No-op experiment tracker for tests and disabled tracking."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class NoOpExperimentTracker:
    @contextmanager
    def start_run(
        self,
        *,
        run_name: str,
        experiment_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Iterator[NoOpExperimentTracker]:
        del run_name, experiment_name, tags
        yield self

    @contextmanager
    def start_nested_run(
        self,
        name: str,
        tags: dict[str, str] | None = None,
    ) -> Iterator[NoOpExperimentTracker]:
        del name, tags
        yield self

    def log_param(self, key: str, value: str | int | float | bool) -> None:
        del key, value

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        del key, value, step

    def log_artifact(self, local_path: str | Path) -> None:
        del local_path

    def set_tag(self, key: str, value: str) -> None:
        del key, value
