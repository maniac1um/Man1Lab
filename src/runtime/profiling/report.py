"""Runtime profiling report formatting."""

from __future__ import annotations

from dataclasses import dataclass

from runtime.profiling.timeline import RuntimeTimeline


@dataclass(frozen=True)
class SessionProfileInfo:
    """Optional session metadata for profiling output."""

    state: str
    duration_s: float | None = None


@dataclass(frozen=True)
class RuntimeProfile:
    """Formatted runtime profiling result."""

    timeline: RuntimeTimeline
    total_ms: float
    resource_statuses: tuple[tuple[str, str], ...] = ()
    session_info: SessionProfileInfo | None = None

    def format_report(self, *, label_width: int = 22) -> str:
        lines = ["Runtime Profile", ""]
        for stage in self.timeline.root_stages():
            lines.append(_format_stage_line(stage, label_width=label_width, indent=0))
            for child in stage.children:
                lines.append(_format_stage_line(child, label_width=label_width, indent=2))
        lines.append("")
        lines.append(_format_stage_line(_TotalStage(), label_width=label_width, indent=0, duration_ms=self.total_ms))
        if self.resource_statuses:
            lines.extend(["", "Runtime Resources", ""])
            for name, status in self.resource_statuses:
                lines.append(_format_resource_line(name, status, label_width=label_width))
        if self.session_info is not None:
            lines.extend(["", "Session", ""])
            lines.append(
                _format_resource_line("State", self.session_info.state, label_width=label_width)
            )
            if self.session_info.duration_s is not None:
                lines.append(
                    _format_resource_line(
                        "Duration",
                        f"{self.session_info.duration_s:.1f} s",
                        label_width=label_width,
                    )
                )
        return "\n".join(lines)

    @property
    def stages(self) -> tuple:
        return self.timeline.root_stages()


@dataclass(frozen=True)
class _TotalStage:
    name: str = "Total"


def _format_stage_line(
    stage,
    *,
    label_width: int,
    indent: int,
    duration_ms: float | None = None,
) -> str:
    prefix = " " * indent
    name = stage.name
    duration = duration_ms if duration_ms is not None else stage.duration_ms
    dots_count = max(1, label_width - len(name) - 1)
    return f"{prefix}{name} {'.' * dots_count} {duration:.1f} ms"


def _format_resource_line(name: str, status: str, *, label_width: int) -> str:
    dots_count = max(1, label_width - len(name) - 1)
    return f"{name} {'.' * dots_count} {status}"
