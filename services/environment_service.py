import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from models.execution import ExecutionResult
from models.workspace import Workspace
from services.exceptions import RequirementsNotFoundError

logger = logging.getLogger(__name__)

LOG_FILENAME = "environment_preparation.log"
VENV_DIRNAME = ".venv"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


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


class EnvironmentService:
    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner or default_command_runner

    def prepare(self, workspace: Workspace) -> ExecutionResult:
        workspace_path = workspace.root_path.resolve()
        requirements_path = workspace_path / "requirements.txt"
        if not requirements_path.exists():
            raise RequirementsNotFoundError(
                f"requirements.txt not found in workspace: {workspace_path}"
            )

        venv_path = workspace_path / VENV_DIRNAME
        pip_path = self._pip_executable(venv_path)
        venv_command = [sys.executable, "-m", "venv", str(venv_path)]
        pip_command = [str(pip_path), "install", "-r", str(requirements_path)]
        executed_command = (
            f"{' '.join(venv_command)} && {' '.join(pip_command)}"
        )

        start = time.perf_counter()
        log_lines = [
            f"Environment preparation started at {self._timestamp()}",
            f"Workspace: {workspace_path}",
            "",
        ]

        venv_result = self._run_step(
            log_lines,
            step_name="virtual environment creation",
            command=venv_command,
            cwd=workspace_path,
        )
        pip_result = self._run_step(
            log_lines,
            step_name="dependency installation",
            command=pip_command,
            cwd=workspace_path,
        )

        duration = time.perf_counter() - start
        success = venv_result.returncode == 0 and pip_result.returncode == 0
        status = "SUCCESS" if success else "FAILED"
        log_lines.extend(
            [
                "",
                f"Status: {status}",
                f"Duration: {duration:.2f}s",
                f"Completed at {self._timestamp()}",
            ]
        )
        self._write_log(workspace_path, log_lines)

        stdout = "\n".join(
            part
            for part in (venv_result.stdout.strip(), pip_result.stdout.strip())
            if part
        )
        stderr = "\n".join(
            part
            for part in (venv_result.stderr.strip(), pip_result.stderr.strip())
            if part
        )
        exit_code = 0 if success else max(venv_result.returncode, pip_result.returncode)

        logger.info(
            "Environment preparation %s for %s in %.2fs",
            status,
            workspace_path,
            duration,
        )

        return ExecutionResult(
            exit_code=exit_code,
            stdout=stdout + ("\n" if stdout else ""),
            stderr=stderr + ("\n" if stderr else ""),
            executed_command=executed_command,
            execution_time_seconds=duration,
            workspace_path=workspace_path,
        )

    def _run_step(
        self,
        log_lines: list[str],
        *,
        step_name: str,
        command: list[str],
        cwd: Path,
    ) -> CommandResult:
        step_start = time.perf_counter()
        log_lines.extend(
            [
                f"## {step_name}",
                f"Command: {' '.join(command)}",
                f"Started at {self._timestamp()}",
            ]
        )
        result = self._command_runner(command, cwd)
        step_duration = time.perf_counter() - step_start
        step_status = "SUCCESS" if result.returncode == 0 else "FAILED"
        log_lines.extend(
            [
                f"Status: {step_status}",
                f"Exit code: {result.returncode}",
                f"Duration: {step_duration:.2f}s",
                "",
            ]
        )
        if result.stdout.strip():
            log_lines.append("Stdout:")
            log_lines.append(result.stdout.strip())
            log_lines.append("")
        if result.stderr.strip():
            log_lines.append("Stderr:")
            log_lines.append(result.stderr.strip())
            log_lines.append("")
        return result

    @staticmethod
    def _pip_executable(venv_path: Path) -> Path:
        scripts_dir = "Scripts" if os.name == "nt" else "bin"
        pip_name = "pip.exe" if os.name == "nt" else "pip"
        return venv_path / scripts_dir / pip_name

    @staticmethod
    def _write_log(workspace_path: Path, log_lines: list[str]) -> None:
        logs_dir = workspace_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / LOG_FILENAME
        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().isoformat(timespec="seconds")
