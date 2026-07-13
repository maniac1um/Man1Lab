"""Tests for canonical execution engine models."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from models.execution_engine import (
    SCHEMA_VERSION,
    Attempt,
    ExecutionArtifactReference,
    ExecutionError,
    ExecutionReport,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTask,
    ExecutionTaskStatus,
    ExecutionTaskType,
    ExecutionTrace,
    LogReference,
    Metric,
    OutputDeclaration,
    TaskExecutionResult,
    TaskResultSummary,
    TraceEvent,
    TraceEventType,
)


class ExecutionEngineModelsTest(unittest.TestCase):
    def test_enums_use_stable_lowercase_values(self) -> None:
        self.assertEqual(ExecutionTaskType.CONFIGURATION.value, "configuration")
        self.assertEqual(ExecutionTaskStatus.PENDING.value, "pending")
        self.assertEqual(TraceEventType.TASK_CREATED.value, "task_created")

    def test_models_are_frozen(self) -> None:
        task = ExecutionTask(
            id="task-1",
            name="Prepare",
            type=ExecutionTaskType.ENVIRONMENT,
        )
        with self.assertRaises(ValidationError):
            task.status = ExecutionTaskStatus.RUNNING  # type: ignore[misc]

    def test_schema_version_defaults(self) -> None:
        result = TaskExecutionResult(
            result_id="res-1",
            run_id="run-1",
            task_id="task-1",
            status=ExecutionTaskStatus.SUCCESS,
            attempts=(Attempt(attempt_id="att-1", task_id="task-1"),),
            task_result=TaskResultSummary(termination_reason="completed"),
        )
        self.assertEqual(result.schema_version, SCHEMA_VERSION)

    def test_metadata_boundaries(self) -> None:
        metadata = {f"key-{index}": "x" for index in range(65)}
        with self.assertRaises(ValidationError):
            ExecutionTask(
                id="task-1",
                name="Prepare",
                type=ExecutionTaskType.ENVIRONMENT,
                metadata=metadata,
            )

    def test_serialization_round_trip(self) -> None:
        now = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)
        trace = ExecutionTrace(
            trace_id="trace-1",
            run_id="run-1",
            created_at=now,
            updated_at=now,
            events=(
                TraceEvent(
                    event_id="evt-1",
                    event_type=TraceEventType.RUN_STARTED,
                    run_id="run-1",
                    sequence=0,
                    recorded_at=now,
                ),
            ),
        )
        payload = trace.model_dump(mode="json")
        restored = ExecutionTrace.model_validate(payload)
        self.assertEqual(restored.events[0].event_type, TraceEventType.RUN_STARTED)

    def test_task_execution_result_supports_full_shape(self) -> None:
        now = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)
        result = TaskExecutionResult(
            result_id="res-1",
            run_id="run-1",
            task_id="task-1",
            status=ExecutionTaskStatus.SUCCESS,
            attempts=(
                Attempt(
                    attempt_id="att-1",
                    task_id="task-1",
                    started_at=now,
                    completed_at=now,
                ),
            ),
            task_result=TaskResultSummary(termination_reason="completed", exit_code=0),
            logs=(
                LogReference(log_id="log-1", excerpt="short"),
            ),
            artifact_ids=("art-1",),
            errors=(
                ExecutionError(code="none", message="clean"),
            ),
            metrics=(
                Metric(name="loss", value=0.1, unit="nats"),
            ),
        )
        self.assertEqual(result.status, ExecutionTaskStatus.SUCCESS)

    def test_execution_run_and_report(self) -> None:
        now = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)
        run = ExecutionRun(
            run_id="run-1",
            graph_id="graph-1",
            strategy_id="strategy-1",
            status=ExecutionRunStatus.SUCCESS,
            created_at=now,
            completed_at=now,
        )
        report = ExecutionReport(
            report_id="report-1",
            run_id=run.run_id,
            graph_id=run.graph_id,
            strategy_id=run.strategy_id,
            status=run.status,
            status_counts={"success": 1},
        )
        self.assertEqual(report.run_id, "run-1")

    def test_input_output_reference_models(self) -> None:
        ref = ExecutionArtifactReference(
            logical_name="dataset",
            artifact_type="dataset",
            required=True,
        )
        output = OutputDeclaration(logical_name="dataset", artifact_type="dataset")
        self.assertTrue(ref.required)
        self.assertTrue(output.required)


if __name__ == "__main__":
    unittest.main()
