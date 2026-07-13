"""Local subprocess executor backend."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from execution.ports.executor import (
    ArtifactCandidate,
    TaskAttemptOutcome,
    TaskAttemptRequest,
)
from models.execution_engine import ExecutionError, ExecutionTask, LogReference, MAX_METADATA_VALUE_LEN


@dataclass(frozen=True)
class LocalInvocation:
    """Backend-local invocation details parsed from task metadata."""

    command: tuple[str, ...]
    working_directory: Path
    environment_variables: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float | None = None


class LocalExecutor:
    """Execute one task attempt as a local subprocess."""

    backend_kind = "local"

    def __init__(
        self,
        *,
        logs_root: Path | None = None,
        default_working_directory: Path | None = None,
        default_timeout_seconds: float | None = None,
        default_environment: dict[str, str] | None = None,
    ) -> None:
        self._logs_root = logs_root
        self._default_working_directory = default_working_directory or Path.cwd()
        self._default_timeout_seconds = default_timeout_seconds
        self._default_environment = dict(default_environment or {})
        self._active_processes: dict[str, subprocess.Popen[str]] = {}

    def execute_attempt(self, request: TaskAttemptRequest) -> TaskAttemptOutcome:
        started_at = datetime.now(UTC)
        start_perf = time.perf_counter()
        try:
            invocation = parse_local_invocation(
                request.task,
                default_working_directory=self._default_working_directory,
                default_timeout_seconds=self._default_timeout_seconds,
                default_environment=self._default_environment,
            )
        except ValueError as exc:
            completed_at = datetime.now(UTC)
            return _failure_outcome(
                request=request,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=time.perf_counter() - start_perf,
                termination_reason="invalid_invocation",
                errors=(
                    ExecutionError(
                        code="invalid_invocation",
                        message=str(exc),
                        phase="dispatch",
                        retryable=False,
                        causal_task_id=request.task.id,
                        causal_attempt_id=request.attempt_id,
                    ),
                ),
            )

        env = os.environ.copy()
        env.update(invocation.environment_variables)
        command = list(invocation.command)
        cwd = invocation.working_directory
        logs_dir = _resolve_logs_dir(request, self._logs_root)

        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._active_processes[request.attempt_id] = process
            stdout, stderr = process.communicate(timeout=invocation.timeout_seconds)
            exit_code = process.returncode
        except FileNotFoundError as exc:
            completed_at = datetime.now(UTC)
            return _failure_outcome(
                request=request,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=time.perf_counter() - start_perf,
                termination_reason="command_not_found",
                errors=(
                    ExecutionError(
                        code="command_not_found",
                        message=f"executable not found: {command[0]}",
                        phase="execution",
                        retryable=False,
                        causal_task_id=request.task.id,
                        causal_attempt_id=request.attempt_id,
                        backend_details={"executable": command[0], "error": str(exc)},
                    ),
                ),
            )
        except subprocess.TimeoutExpired:
            completed_at = datetime.now(UTC)
            stdout_text = ""
            stderr_text = ""
            exit_code: int | None = None
            if process is not None:
                process.kill()
                try:
                    stdout_text, stderr_text = process.communicate(timeout=5)
                except Exception:
                    stdout_text = ""
                    stderr_text = ""
                exit_code = process.returncode
            logs = _write_stream_logs(
                logs_dir=logs_dir,
                attempt_id=request.attempt_id,
                stdout=stdout_text,
                stderr=stderr_text,
                recorded_at=completed_at,
            )
            pid = str(process.pid) if process is not None else ""
            return TaskAttemptOutcome(
                termination_reason="timeout",
                succeeded=False,
                exit_code=exit_code,
                logs=logs,
                errors=(
                    ExecutionError(
                        code="execution_timeout",
                        message=(
                            f"command exceeded timeout of {invocation.timeout_seconds}s"
                            if invocation.timeout_seconds is not None
                            else "command exceeded timeout"
                        ),
                        phase="execution",
                        retryable=True,
                        causal_task_id=request.task.id,
                        causal_attempt_id=request.attempt_id,
                        backend_details={"pid": pid, "timeout_seconds": str(invocation.timeout_seconds or "")},
                    ),
                ),
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=time.perf_counter() - start_perf,
                backend_kind=self.backend_kind,
                backend_operation_ref=_backend_operation_ref(request.attempt_id, pid),
                backend_metadata=_backend_metadata(command, cwd, pid),
                timed_out=True,
            )
        except OSError as exc:
            completed_at = datetime.now(UTC)
            return _failure_outcome(
                request=request,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=time.perf_counter() - start_perf,
                termination_reason="execution_error",
                errors=(
                    ExecutionError(
                        code="execution_error",
                        message=str(exc),
                        phase="execution",
                        retryable=False,
                        causal_task_id=request.task.id,
                        causal_attempt_id=request.attempt_id,
                        backend_details={"executable": command[0]},
                    ),
                ),
            )
        except Exception as exc:
            completed_at = datetime.now(UTC)
            return _failure_outcome(
                request=request,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=time.perf_counter() - start_perf,
                termination_reason="unexpected_exception",
                errors=(
                    ExecutionError(
                        code="execution_exception",
                        message=str(exc),
                        phase="execution",
                        retryable=False,
                        causal_task_id=request.task.id,
                        causal_attempt_id=request.attempt_id,
                    ),
                ),
            )
        finally:
            self._active_processes.pop(request.attempt_id, None)

        completed_at = datetime.now(UTC)
        duration_seconds = time.perf_counter() - start_perf
        pid = str(process.pid) if process is not None else ""
        logs = _write_stream_logs(
            logs_dir=logs_dir,
            attempt_id=request.attempt_id,
            stdout=stdout,
            stderr=stderr,
            recorded_at=completed_at,
        )

        if exit_code != 0:
            return TaskAttemptOutcome(
                termination_reason="nonzero_exit",
                succeeded=False,
                exit_code=exit_code,
                logs=logs,
                errors=(
                    ExecutionError(
                        code="nonzero_exit_code",
                        message=f"command exited with code {exit_code}",
                        phase="execution",
                        retryable=False,
                        causal_task_id=request.task.id,
                        causal_attempt_id=request.attempt_id,
                        backend_details={"pid": pid, "exit_code": str(exit_code)},
                    ),
                ),
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                backend_kind=self.backend_kind,
                backend_operation_ref=_backend_operation_ref(request.attempt_id, pid),
                backend_metadata=_backend_metadata(command, cwd, pid),
            )

        artifact_candidates = _collect_artifact_candidates(
            request=request,
            working_directory=cwd,
            declared_outputs=request.declared_outputs or request.task.outputs,
        )
        return TaskAttemptOutcome(
            termination_reason="completed",
            succeeded=True,
            exit_code=exit_code,
            logs=logs,
            artifact_candidates=artifact_candidates,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            backend_kind=self.backend_kind,
            backend_operation_ref=_backend_operation_ref(request.attempt_id, pid),
            backend_metadata=_backend_metadata(command, cwd, pid),
        )

    def active_process(self, attempt_id: str) -> subprocess.Popen[str] | None:
        """Return the in-flight process handle for future cancellation support."""
        return self._active_processes.get(attempt_id)


def parse_local_invocation(
    task: ExecutionTask,
    *,
    default_working_directory: Path,
    default_timeout_seconds: float | None = None,
    default_environment: dict[str, str] | None = None,
) -> LocalInvocation:
    """Parse backend-local invocation fields from canonical task metadata."""
    metadata = task.metadata
    command_raw = metadata.get("command", "")
    if not command_raw.strip():
        raise ValueError("task metadata must include non-empty 'command'")

    command = _parse_command(command_raw)
    working_directory = _parse_working_directory(
        metadata.get("working_directory", ""),
        default=default_working_directory,
    )
    environment_variables = dict(default_environment or {})
    environment_variables.update(_parse_environment(metadata.get("environment_variables", "")))
    environment_variables.update(_parse_environment(metadata.get("env", "")))
    timeout_seconds = _parse_timeout(
        metadata.get("timeout_seconds", ""),
        default=default_timeout_seconds,
    )
    return LocalInvocation(
        command=command,
        working_directory=working_directory,
        environment_variables=environment_variables,
        timeout_seconds=timeout_seconds,
    )


def _parse_command(raw: str) -> tuple[str, ...]:
    parsed = _parse_json_value(raw, field_name="command")
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("command metadata must be a non-empty JSON array of strings")
    if not all(isinstance(item, str) and item for item in parsed):
        raise ValueError("command metadata must contain only non-empty strings")
    return tuple(parsed)


def _parse_working_directory(raw: str, *, default: Path) -> Path:
    if not raw.strip():
        return default.resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = (default / path).resolve()
    else:
        path = path.resolve()
    return path


def _parse_environment(raw: str) -> dict[str, str]:
    if not raw.strip():
        return {}
    parsed = _parse_json_value(raw, field_name="environment")
    if not isinstance(parsed, dict):
        raise ValueError("environment metadata must be a JSON object")
    result: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("environment metadata must contain only string keys and values")
        result[key] = value
    return result


def _parse_timeout(raw: str, *, default: float | None) -> float | None:
    if not raw.strip():
        return default
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise ValueError("timeout_seconds metadata must be numeric") from exc
    if timeout <= 0:
        raise ValueError("timeout_seconds must be positive")
    return timeout


def _parse_json_value(raw: str, *, field_name: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} metadata must be valid JSON") from exc


def _resolve_logs_dir(request: TaskAttemptRequest, logs_root: Path | None) -> Path:
    if request.logs_dir.strip():
        logs_dir = Path(request.logs_dir)
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir
    if logs_root is not None:
        logs_dir = logs_root / request.run_id / request.attempt_id
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir
    raise ValueError(
        "attempt logs_dir must be provided via TaskAttemptRequest.logs_dir "
        "or LocalExecutor(logs_root=...) at composition time"
    )


def _bounded_excerpt(text: str) -> str:
    if len(text) <= MAX_METADATA_VALUE_LEN:
        return text
    return text[: MAX_METADATA_VALUE_LEN - 3] + "..."


def _write_stream_logs(
    *,
    logs_dir: Path,
    attempt_id: str,
    stdout: str,
    stderr: str,
    recorded_at: datetime,
) -> tuple[LogReference, ...]:
    logs: list[LogReference] = []
    for stream, content in (("stdout", stdout), ("stderr", stderr)):
        log_path = logs_dir / f"{stream}.log"
        log_path.write_text(content, encoding="utf-8")
        logs.append(
            LogReference(
                log_id=f"log-{attempt_id}-{stream}",
                stream=stream,
                location_ref=log_path.as_posix(),
                size_bytes=len(content.encode("utf-8")),
                recorded_at=recorded_at,
                excerpt=_bounded_excerpt(content),
            )
        )
    return tuple(logs)


def _collect_artifact_candidates(
    *,
    request: TaskAttemptRequest,
    working_directory: Path,
    declared_outputs: tuple[Any, ...],
) -> tuple[ArtifactCandidate, ...]:
    metadata_paths = request.task.metadata.get("artifact_paths", "")
    path_map: dict[str, str] = {}
    if metadata_paths.strip():
        parsed = _parse_json_value(metadata_paths, field_name="artifact_paths")
        if not isinstance(parsed, dict):
            raise ValueError("artifact_paths metadata must be a JSON object")
        for key, value in parsed.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("artifact_paths metadata must contain string keys and values")
            path_map[key] = value

    candidates: list[ArtifactCandidate] = []
    for output in declared_outputs:
        relative_path = path_map.get(output.logical_name, "")
        if not relative_path:
            continue
        artifact_path = Path(relative_path)
        if not artifact_path.is_absolute():
            artifact_path = (working_directory / artifact_path).resolve()
        if not artifact_path.is_file():
            continue
        candidates.append(
            ArtifactCandidate(
                logical_name=output.logical_name,
                artifact_type=output.artifact_type,
                location_ref=artifact_path.as_posix(),
                size_bytes=artifact_path.stat().st_size,
            )
        )
    return tuple(candidates)


def _backend_operation_ref(attempt_id: str, pid: str) -> str:
    if pid:
        return f"local-{attempt_id}-pid-{pid}"
    return f"local-{attempt_id}"


def _backend_metadata(command: list[str], cwd: Path, pid: str) -> dict[str, str]:
    metadata = {
        "command": " ".join(command)[:MAX_METADATA_VALUE_LEN],
        "working_directory": cwd.as_posix(),
    }
    if pid:
        metadata["pid"] = pid
    return metadata


def _failure_outcome(
    *,
    request: TaskAttemptRequest,
    started_at: datetime,
    completed_at: datetime,
    duration_seconds: float,
    termination_reason: str,
    errors: tuple[ExecutionError, ...],
) -> TaskAttemptOutcome:
    return TaskAttemptOutcome(
        termination_reason=termination_reason,
        succeeded=False,
        exit_code=None,
        errors=errors,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=duration_seconds,
        backend_kind=LocalExecutor.backend_kind,
        backend_operation_ref=_backend_operation_ref(request.attempt_id, ""),
    )