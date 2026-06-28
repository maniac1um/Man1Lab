from models.execution import ExecutionResult
from models.workspace import Workspace


class Runner:
    def run(self, workspace: Workspace) -> ExecutionResult:
        return ExecutionResult(
            exit_code=0,
            stdout="Training complete.\n",
            stderr="",
            executed_command="python scripts/train.py",
            execution_time_seconds=1.2,
            workspace_path=workspace.root_path,
        )
