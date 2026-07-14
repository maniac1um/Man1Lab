"""Hierarchical runtime profiler."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from runtime.profiling.measurements import StageMeasurement
from runtime.profiling.report import RuntimeProfile, SessionProfileInfo
from runtime.profiling.timeline import RuntimeTimeline


@dataclass
class _ActiveStage:
    name: str
    order: int
    started_at: float
    children: list[StageMeasurement] = field(default_factory=list)


class RuntimeProfiler:
    """Record hierarchical timing measurements without global state."""

    def __init__(self) -> None:
        self._started_at = time.perf_counter()
        self._order_counter = 0
        self._stack: list[_ActiveStage] = []
        self._root_stages: list[StageMeasurement] = []

    def begin_stage(self, name: str) -> None:
        self._order_counter += 1
        self._stack.append(
            _ActiveStage(
                name=name,
                order=self._order_counter,
                started_at=time.perf_counter(),
            )
        )

    def end_stage(self) -> StageMeasurement:
        if not self._stack:
            raise RuntimeError("end_stage() called without a matching begin_stage().")

        active = self._stack.pop()
        duration_ms = (time.perf_counter() - active.started_at) * 1000.0
        measurement = StageMeasurement(
            name=active.name,
            duration_ms=duration_ms,
            order=active.order,
            children=tuple(active.children),
        )

        if self._stack:
            self._stack[-1].children.append(measurement)
        else:
            self._root_stages.append(measurement)
        return measurement

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        self.begin_stage(name)
        try:
            yield
        finally:
            self.end_stage()

    def build_profile(
        self,
        *,
        resource_statuses: tuple[tuple[str, str], ...] = (),
        session_info: SessionProfileInfo | None = None,
    ) -> RuntimeProfile:
        total_ms = (time.perf_counter() - self._started_at) * 1000.0
        timeline = RuntimeTimeline(stages=tuple(self._root_stages))
        return RuntimeProfile(
            timeline=timeline,
            total_ms=total_ms,
            resource_statuses=resource_statuses,
            session_info=session_info,
        )

    def build_timeline(self) -> RuntimeTimeline:
        return RuntimeTimeline(stages=tuple(self._root_stages))
