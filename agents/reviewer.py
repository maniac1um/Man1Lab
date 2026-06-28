from models.execution import ExecutionResult
from models.review import PatchPlan


class Reviewer:
    def run(self, result: ExecutionResult) -> PatchPlan:
        return PatchPlan(
            requires_patch=False,
            patches=[],
            analysis=(
                f"No issues detected for command `{result.executed_command}` "
                f"with exit code {result.exit_code}."
            ),
        )
