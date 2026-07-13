"""Durable transition journal for crash-consistent multi-file commits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from execution.errors import CorruptSnapshotError, PersistenceIOError
from models.execution_engine import (
    SCHEMA_VERSION,
    Artifact,
    ExecutionReport,
    ExecutionRun,
    ExecutionTask,
    TaskExecutionResult,
    TraceEvent,
)
from runtime.execution_store.atomic_io import atomic_write_json, load_json


JOURNAL_DIR = "journal"
JOURNAL_SUFFIX = ".journal.json"


class JournalStatus(str, Enum):
    NOT_STARTED = "not_started"
    JOURNAL_DURABLE = "journal_durable"
    SNAPSHOTS_PARTIAL = "snapshots_partial"
    SNAPSHOTS_COMPLETE = "snapshots_complete"
    COMMITTED = "committed"


SNAPSHOT_FILE_ORDER = ("tasks.json", "artifacts.json", "report.json")


@dataclass(frozen=True)
class TransitionJournalRecord:
    transition_id: str
    run_id: str
    base_revision: int
    target_revision: int
    status: JournalStatus
    updated_snapshots: tuple[str, ...]
    trace_events: tuple[TraceEvent, ...]
    run: ExecutionRun
    tasks: tuple[ExecutionTask, ...]
    task_results: tuple[TaskExecutionResult, ...]
    artifacts: tuple[Artifact, ...]
    report: ExecutionReport | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "transition_id": self.transition_id,
            "run_id": self.run_id,
            "base_revision": self.base_revision,
            "target_revision": self.target_revision,
            "status": self.status.value,
            "updated_snapshots": list(self.updated_snapshots),
            "trace_events": [event.model_dump(mode="json") for event in self.trace_events],
            "run": self.run.model_dump(mode="json"),
            "tasks": [task.model_dump(mode="json") for task in self.tasks],
            "task_results": [result.model_dump(mode="json") for result in self.task_results],
            "artifacts": [artifact.model_dump(mode="json") for artifact in self.artifacts],
            "report": self.report.model_dump(mode="json") if self.report is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TransitionJournalRecord:
        try:
            status = JournalStatus(str(payload["status"]))
        except (KeyError, ValueError) as exc:
            raise CorruptSnapshotError("invalid journal status") from exc
        trace_events = tuple(
            TraceEvent.model_validate(item) for item in payload.get("trace_events", [])
        )
        tasks = tuple(ExecutionTask.model_validate(item) for item in payload.get("tasks", []))
        task_results = tuple(
            TaskExecutionResult.model_validate(item) for item in payload.get("task_results", [])
        )
        artifacts = tuple(
            Artifact.model_validate(item) for item in payload.get("artifacts", [])
        )
        report_payload = payload.get("report")
        report = ExecutionReport.model_validate(report_payload) if report_payload else None
        updated = payload.get("updated_snapshots", [])
        return cls(
            transition_id=str(payload["transition_id"]),
            run_id=str(payload["run_id"]),
            base_revision=int(payload["base_revision"]),
            target_revision=int(payload["target_revision"]),
            status=status,
            updated_snapshots=tuple(str(item) for item in updated),
            trace_events=trace_events,
            run=ExecutionRun.model_validate(payload["run"]),
            tasks=tasks,
            task_results=task_results,
            artifacts=artifacts,
            report=report,
        )


def journal_path(run_dir: Path, transition_id: str) -> Path:
    if (
        not transition_id
        or transition_id in {".", ".."}
        or "/" in transition_id
        or "\\" in transition_id
        or ".." in transition_id
    ):
        raise PersistenceIOError("invalid transition_id for journal path")
    return run_dir / JOURNAL_DIR / f"{transition_id}{JOURNAL_SUFFIX}"


def list_incomplete_journals(run_dir: Path) -> list[TransitionJournalRecord]:
    journal_root = run_dir / JOURNAL_DIR
    if not journal_root.is_dir():
        return []
    records: list[TransitionJournalRecord] = []
    for path in sorted(journal_root.glob(f"*{JOURNAL_SUFFIX}")):
        record = TransitionJournalRecord.from_dict(load_json(path))
        if record.transition_id != path.name[: -len(JOURNAL_SUFFIX)]:
            raise CorruptSnapshotError(f"journal filename/transition mismatch: {path}")
        if record.status != JournalStatus.COMMITTED:
            records.append(record)
    return records


def write_journal(path: Path, record: TransitionJournalRecord) -> None:
    atomic_write_json(path, record.to_dict())


def remove_journal(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise PersistenceIOError(f"failed to remove journal {path}: {exc}") from exc
