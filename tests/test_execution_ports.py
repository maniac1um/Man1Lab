"""Tests for executor and artifact tracker ports."""

from __future__ import annotations

import unittest

from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.backends.fake_executor import FakeExecutor, FakeExecutorRule
from execution.errors import ArtifactValidationError
from execution.ports.executor import ArtifactCandidate, TaskAttemptRequest
from models.execution_engine import ExecutionTask, ExecutionTaskType, OutputDeclaration


class ExecutionPortsTest(unittest.TestCase):
    def test_fake_executor_returns_candidates_for_declared_outputs(self) -> None:
        task = ExecutionTask(
            id="task-1",
            name="Training",
            type=ExecutionTaskType.TRAINING,
            outputs=(
                OutputDeclaration(logical_name="training_output", artifact_type="training"),
            ),
        )
        executor = FakeExecutor()
        outcome = executor.execute_attempt(
            TaskAttemptRequest(
                run_id="run-1",
                task=task,
                attempt_id="att-1",
                declared_outputs=task.outputs,
            )
        )
        self.assertTrue(outcome.succeeded)
        self.assertEqual(len(outcome.artifact_candidates), 1)
        self.assertEqual(outcome.artifact_candidates[0].logical_name, "training_output")

    def test_fake_executor_failure_rule(self) -> None:
        task = ExecutionTask(id="task-1", name="Training", type=ExecutionTaskType.TRAINING)
        executor = FakeExecutor(rules_by_task_id={"task-1": FakeExecutorRule(succeed=False)})
        outcome = executor.execute_attempt(
            TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-1")
        )
        self.assertFalse(outcome.succeeded)
        self.assertEqual(len(outcome.errors), 1)

    def test_in_memory_artifact_tracker_registers_and_validates(self) -> None:
        tracker = InMemoryArtifactTracker()
        artifact = tracker.register_candidate(
            run_id="run-1",
            task_id="task-1",
            attempt_id="att-1",
            candidate=ArtifactCandidate(logical_name="dataset", artifact_type="dataset"),
        )
        validated = tracker.validate_required_outputs(
            run_id="run-1",
            task_id="task-1",
            attempt_id="att-1",
            declarations=(
                OutputDeclaration(logical_name="dataset", artifact_type="dataset", required=True),
            ),
        )
        self.assertEqual(validated[0].artifact_id, artifact.artifact_id)
        self.assertTrue(tracker.artifact_still_valid(artifact.artifact_id))

    def test_in_memory_artifact_invalidation(self) -> None:
        tracker = InMemoryArtifactTracker()
        artifact = tracker.register_candidate(
            run_id="run-1",
            task_id="task-1",
            attempt_id="att-1",
            candidate=ArtifactCandidate(logical_name="dataset", artifact_type="dataset"),
        )
        tracker.invalidate(artifact.artifact_id, reason="missing")
        self.assertFalse(tracker.artifact_still_valid(artifact.artifact_id))
        with self.assertRaises(ArtifactValidationError):
            tracker.validate_required_outputs(
                run_id="run-1",
                task_id="task-1",
                attempt_id="att-1",
                declarations=(
                    OutputDeclaration(logical_name="dataset", artifact_type="dataset", required=True),
                ),
            )


if __name__ == "__main__":
    unittest.main()
