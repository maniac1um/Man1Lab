"""Experiment tracking bootstrap."""

from __future__ import annotations

from configuration.models import AppSettings, TrackingConfig
from tracking.mlflow_tracker import MLflowExperimentTracker
from tracking.noop_tracker import NoOpExperimentTracker
from tracking.protocol import ExperimentTracker
from tracking.provider import set_experiment_tracker


def build_experiment_tracker(settings: TrackingConfig) -> ExperimentTracker:
    if not settings.enabled or settings.backend == "noop":
        return NoOpExperimentTracker()

    if settings.backend == "mlflow":
        return MLflowExperimentTracker(
            tracking_uri=settings.tracking_uri,
            experiment_name=settings.experiment_name,
        )

    raise ValueError(f"Unsupported tracking backend: {settings.backend}")


def initialize_experiment_tracking(settings: AppSettings) -> ExperimentTracker:
    tracker = build_experiment_tracker(settings.tracking)
    set_experiment_tracker(tracker)
    return tracker
