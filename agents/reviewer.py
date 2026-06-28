from models.execution import ExecutionResult
from models.verification import VerificationResult
from models.workspace import Workspace
from services.verification_service import VerificationService


class Reviewer:
    def __init__(self, verification_service: VerificationService | None = None) -> None:
        self._verification_service = verification_service or VerificationService()

    def run(
        self,
        workspace: Workspace,
        execution_result: ExecutionResult,
    ) -> VerificationResult:
        return self._verification_service.verify(workspace, execution_result)
