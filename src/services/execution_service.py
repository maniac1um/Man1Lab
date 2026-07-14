import logging
import os
import subprocess
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from models.execution import ExecutionResult
from models.execution_plan import ExecutionPlan
from models.workspace import Workspace
from services.environment_service import CommandResult

logger = logging.getLogger(__name__)

LOG_FILENAME = "execution.log"

CommandRunner = Callable[[list[str], Path], CommandResult]


def default_command_runner(command: list[str], cwd: Path) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


class ExecutionService:
    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner or default_command_runner

    def execute(self, plan: ExecutionPlan, workspace: Workspace) -> ExecutionResult:
        workspace_path = workspace.root_path.resolve()
        executed_command = " ".join(plan.command)
        start_time = self._timestamp()
        start = time.perf_counter()

        result = self._run_plan(plan)
        duration = time.perf_counter() - start
        end_time = self._timestamp()
        status = "SUCCESS" if result.returncode == 0 else "FAILED"

        log_lines = [
            f"Script execution started at {start_time}",
            f"Workspace: {workspace_path}",
            f"Command: {executed_command}",
            f"Working directory: {plan.working_directory}",
            f"Ended at {end_time}",
            f"Duration: {duration:.2f}s",
            f"Exit code: {result.returncode}",
            f"Status: {status}",
            "",
        ]
        if result.stdout.strip():
            log_lines.extend(["Stdout:", result.stdout.strip(), ""])
        if result.stderr.strip():
            log_lines.extend(["Stderr:", result.stderr.strip(), ""])

        self._write_log(workspace_path, log_lines)

        logger.info(
            "Script execution %s for %s in %.2fs (exit %s)",
            status,
            workspace_path,
            duration,
            result.returncode,
        )

        return ExecutionResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            executed_command=executed_command,
            execution_time_seconds=duration,
            workspace_path=workspace_path,
        )

    def _run_plan(self, plan: ExecutionPlan) -> CommandResult:
        if self._command_runner is not default_command_runner:
            return self._command_runner(plan.command, plan.working_directory)
        if plan.environment_variables:
            return self._run_with_environment(plan)
        return self._command_runner(plan.command, plan.working_directory)

    def _run_with_environment(self, plan: ExecutionPlan) -> CommandResult:
        env = os.environ.copy()
        env.update(plan.environment_variables)
        completed = subprocess.run(
            plan.command,
            cwd=plan.working_directory,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    @staticmethod
    def _write_log(workspace_path: Path, log_lines: list[str]) -> None:
        logs_dir = workspace_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / LOG_FILENAME
        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().isoformat(timespec="seconds")
