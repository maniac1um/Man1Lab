"""MLflow-backed experiment tracker — the only module that imports mlflow."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import mlflow


class MLflowExperimentTracker:
    """Thin MLflow adapter implementing ExperimentTracker capabilities only."""

    def __init__(self, *, tracking_uri: str, experiment_name: str) -> None:
        self._experiment_name = experiment_name
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)

    @contextmanager
    def start_run(
        self,
        *,
        run_name: str,
        experiment_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Iterator[MLflowExperimentTracker]:
        if experiment_name:
            mlflow.set_experiment(experiment_name)
        else:
            mlflow.set_experiment(self._experiment_name)

        with mlflow.start_run(run_name=run_name):
            if tags:
                for key, value in tags.items():
                    mlflow.set_tag(key, value)
            yield self

    @contextmanager
    def start_nested_run(
        self,
        name: str,
        tags: dict[str, str] | None = None,
    ) -> Iterator[MLflowExperimentTracker]:
        with mlflow.start_run(run_name=name, nested=True):
            if tags:
                for key, value in tags.items():
                    mlflow.set_tag(key, value)
            yield self

    def log_param(self, key: str, value: str | int | float | bool) -> None:
        mlflow.log_param(key, value)

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        mlflow.log_metric(key, value, step=step)

    def log_artifact(self, local_path: str | Path) -> None:
        path = Path(local_path)
        if path.is_dir():
            mlflow.log_artifacts(str(path))
        elif path.is_file():
            mlflow.log_artifact(str(path))
        else:
            raise FileNotFoundError(f"Artifact path does not exist: {path}")

    def set_tag(self, key: str, value: str) -> None:
        mlflow.set_tag(key, value)
