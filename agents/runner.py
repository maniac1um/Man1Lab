from models.execution import ExecutionResult
from models.workspace import Workspace
from execution.execution_planner import ExecutionPlanner
from services.environment_service import EnvironmentService
from services.execution_service import ExecutionService


class Runner:
    def __init__(
        self,
        environment_service: EnvironmentService | None = None,
        execution_planner: ExecutionPlanner | None = None,
        execution_service: ExecutionService | None = None,
    ) -> None:
        self._environment_service = environment_service or EnvironmentService()
        self._execution_planner = execution_planner or ExecutionPlanner()
        self._execution_service = execution_service or ExecutionService()

    def run(self, workspace: Workspace) -> ExecutionResult:
        prep_result = self._environment_service.prepare(workspace)
        if prep_result.exit_code != 0:
            return prep_result

        plan = self._execution_planner.plan(workspace)
        return self._execution_service.execute(plan, workspace)
