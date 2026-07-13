"""Tests for the local subprocess executor backend."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from execution.backends.local_executor import LocalExecutor, parse_local_invocation
from execution.ports.executor import TaskAttemptRequest
from models.execution_engine import ExecutionTask, ExecutionTaskType, OutputDeclaration


def _python_command_args(script: str) -> str:
    return json.dumps([sys.executable, "-c", script])


def _command_task(
    *,
    task_id: str = "task-local-1",
    command_args: str,
    working_directory: str = "",
    environment_variables: str = "",
    timeout_seconds: str = "",
    artifact_paths: str = "",
) -> ExecutionTask:
    metadata: dict[str, str] = {"command": command_args}
    if working_directory:
        metadata["working_directory"] = working_directory
    if environment_variables:
        metadata["environment_variables"] = environment_variables
    if timeout_seconds:
        metadata["timeout_seconds"] = timeout_seconds
    if artifact_paths:
        metadata["artifact_paths"] = artifact_paths
    return ExecutionTask(
        id=task_id,
        name="Local Command",
        type=ExecutionTaskType.TRAINING,
        metadata=metadata,
    )


class LocalExecutorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.logs_root = self.root / "logs"
        self.executor = LocalExecutor(
            logs_root=self.logs_root,
            default_working_directory=self.root,
        )

    def test_success_prints_hello(self) -> None:
        task = _command_task(command_args=_python_command_args("print('hello')"))
        outcome = self.executor.execute_attempt(
            TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-1")
        )
        self.assertTrue(outcome.succeeded)
        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.termination_reason, "completed")
        self.assertGreater(outcome.duration_seconds or 0.0, 0.0)
        stdout_log = next(log for log in outcome.logs if log.stream == "stdout")
        self.assertIn("hello", stdout_log.excerpt)

    def test_failed_nonzero_exit(self) -> None:
        task = _command_task(command_args=_python_command_args("raise Exception('boom')"))
        outcome = self.executor.execute_attempt(
            TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-2")
        )
        self.assertFalse(outcome.succeeded)
        self.assertNotEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.termination_reason, "nonzero_exit")
        self.assertEqual(len(outcome.errors), 1)
        self.assertEqual(outcome.errors[0].code, "nonzero_exit_code")

    def test_command_not_found(self) -> None:
        task = _command_task(
            command_args=json.dumps(["definitely-not-a-real-executable-xyz", "noop"]),
        )
        outcome = self.executor.execute_attempt(
            TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-3")
        )
        self.assertFalse(outcome.succeeded)
        self.assertEqual(outcome.termination_reason, "command_not_found")
        self.assertEqual(outcome.errors[0].code, "command_not_found")

    def test_stdout_stderr_capture(self) -> None:
        script = (
            "import sys; print('stdout-msg'); "
            "print('stderr-msg', file=sys.stderr)"
        )
        task = _command_task(command_args=_python_command_args(script))
        outcome = self.executor.execute_attempt(
            TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-4")
        )
        self.assertTrue(outcome.succeeded)
        stdout_log = next(log for log in outcome.logs if log.stream == "stdout")
        stderr_log = next(log for log in outcome.logs if log.stream == "stderr")
        self.assertIn("stdout-msg", stdout_log.excerpt)
        self.assertIn("stderr-msg", stderr_log.excerpt)
        self.assertTrue(Path(stdout_log.location_ref).is_file())
        self.assertTrue(Path(stderr_log.location_ref).is_file())
        self.assertIn("pid", outcome.backend_metadata)

    def test_working_directory(self) -> None:
        nested = self.root / "nested"
        nested.mkdir()
        marker = nested / "marker.txt"
        marker.write_text("ok", encoding="utf-8")
        script = "from pathlib import Path; print(Path('marker.txt').read_text())"
        task = _command_task(
            command_args=_python_command_args(script),
            working_directory=str(nested),
        )
        outcome = self.executor.execute_attempt(
            TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-5")
        )
        self.assertTrue(outcome.succeeded)
        stdout_log = next(log for log in outcome.logs if log.stream == "stdout")
        self.assertIn("ok", stdout_log.excerpt)
        self.assertEqual(outcome.backend_metadata["working_directory"], nested.resolve().as_posix())

    def test_environment_variables(self) -> None:
        script = "import os; print(os.environ.get('MAN1LAB_TEST_ENV', ''))"
        task = _command_task(
            command_args=_python_command_args(script),
            environment_variables=json.dumps({"MAN1LAB_TEST_ENV": "local-value"}),
        )
        outcome = self.executor.execute_attempt(
            TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-6")
        )
        self.assertTrue(outcome.succeeded)
        stdout_log = next(log for log in outcome.logs if log.stream == "stdout")
        self.assertIn("local-value", stdout_log.excerpt)

    def test_timeout_behavior(self) -> None:
        script = "import time; time.sleep(2)"
        task = _command_task(
            command_args=_python_command_args(script),
            timeout_seconds="0.2",
        )
        outcome = self.executor.execute_attempt(
            TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-7")
        )
        self.assertFalse(outcome.succeeded)
        self.assertTrue(outcome.timed_out)
        self.assertEqual(outcome.termination_reason, "timeout")
        self.assertEqual(outcome.errors[0].code, "execution_timeout")

    def test_missing_command_metadata(self) -> None:
        task = ExecutionTask(id="task-missing", name="Missing", type=ExecutionTaskType.TRAINING)
        outcome = self.executor.execute_attempt(
            TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-8")
        )
        self.assertFalse(outcome.succeeded)
        self.assertEqual(outcome.errors[0].code, "invalid_invocation")

    def test_artifact_candidates_from_metadata_paths(self) -> None:
        output_file = self.root / "output.txt"
        output_file.write_text("artifact-body", encoding="utf-8")
        task = _command_task(
            command_args=_python_command_args("print('done')"),
            artifact_paths=json.dumps({"training_output": "output.txt"}),
        )
        task = task.model_copy(
            update={
                "outputs": (
                    OutputDeclaration(
                        logical_name="training_output",
                        artifact_type="training",
                        required=False,
                    ),
                )
            }
        )
        outcome = self.executor.execute_attempt(
            TaskAttemptRequest(
                run_id="run-1",
                task=task,
                attempt_id="att-9",
                declared_outputs=task.outputs,
            )
        )
        self.assertTrue(outcome.succeeded)
        self.assertEqual(len(outcome.artifact_candidates), 1)
        self.assertEqual(outcome.artifact_candidates[0].logical_name, "training_output")
        self.assertTrue(Path(outcome.artifact_candidates[0].location_ref).is_file())

    def test_process_handle_not_retained_after_completion(self) -> None:
        task = _command_task(command_args=_python_command_args("print('done')"))
        outcome = self.executor.execute_attempt(
            TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-10")
        )
        self.assertTrue(outcome.succeeded)
        self.assertIsNone(self.executor.active_process("att-10"))

    def test_parse_local_invocation_defaults(self) -> None:
        task = _command_task(command_args=json.dumps(["python", "train.py"]))
        invocation = parse_local_invocation(task, default_working_directory=self.root)
        self.assertEqual(invocation.command, ("python", "train.py"))
        self.assertEqual(invocation.working_directory, self.root.resolve())
        self.assertEqual(invocation.environment_variables, {})


if __name__ == "__main__":
    unittest.main()
