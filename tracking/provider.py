"""Experiment tracker registry."""

from __future__ import annotations

from tracking.noop_tracker import NoOpExperimentTracker
from tracking.protocol import ExperimentTracker

_tracker: ExperimentTracker | None = None


def get_experiment_tracker() -> ExperimentTracker:
    if _tracker is None:
        return NoOpExperimentTracker()
    return _tracker


def set_experiment_tracker(tracker: ExperimentTracker) -> None:
    global _tracker
    _tracker = tracker
