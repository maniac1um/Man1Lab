"""Stage measurement records for runtime profiling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StageMeasurement:
    """A single timed stage, optionally containing nested child stages."""

    name: str
    duration_ms: float
    order: int
    children: tuple[StageMeasurement, ...] = ()

    def flattened(self) -> tuple[StageMeasurement, ...]:
        """Return this stage and all descendants in deterministic depth-first order."""
        ordered: list[StageMeasurement] = [self]
        for child in self.children:
            ordered.extend(child.flattened())
        return tuple(ordered)
