import os
from pathlib import Path

from models.execution_plan import ExecutionPlan
from models.workspace import Workspace
from services.environment_service import VENV_DIRNAME
from services.exceptions import ExecutionPlanError

TRAIN_SCRIPT = "scripts/train.py"


class ExecutionPlanner:
    def plan(self, workspace: Workspace) -> ExecutionPlan:
        workspace_path = workspace.root_path.resolve()
        script_path = workspace_path / TRAIN_SCRIPT
        if not script_path.is_file():
            raise ExecutionPlanError(f"Training script not found: {script_path}")

        venv_path = workspace_path / VENV_DIRNAME
        python_executable = self._venv_python(venv_path)
        return ExecutionPlan(
            command=[str(python_executable), TRAIN_SCRIPT],
            working_directory=workspace_path,
            environment_variables={"VIRTUAL_ENV": str(venv_path)},
        )

    @staticmethod
    def _venv_python(venv_path: Path) -> Path:
        scripts_dir = "Scripts" if os.name == "nt" else "bin"
        python_name = "python.exe" if os.name == "nt" else "python"
        return venv_path / scripts_dir / python_name
