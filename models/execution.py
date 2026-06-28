from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    exit_code: int
    stdout: str
    stderr: str
    executed_command: str
    execution_time_seconds: float
    workspace_path: Path
