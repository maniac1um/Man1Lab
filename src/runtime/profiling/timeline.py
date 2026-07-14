"""Ordered collection of runtime stage measurements."""

from __future__ import annotations

from dataclasses import dataclass

from runtime.profiling.measurements import StageMeasurement


@dataclass(frozen=True)
class RuntimeTimeline:
    """Immutable ordered view of recorded stage measurements."""

    stages: tuple[StageMeasurement, ...]

    def root_stages(self) -> tuple[StageMeasurement, ...]:
        return self.stages

    def flattened(self) -> tuple[StageMeasurement, ...]:
        ordered: list[StageMeasurement] = []
        for stage in self.stages:
            ordered.extend(stage.flattened())
        return tuple(ordered)

    def total_recorded_ms(self) -> float:
        return sum(stage.duration_ms for stage in self.stages)
