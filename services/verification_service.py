from pathlib import Path

from models.execution import ExecutionResult
from models.verification import (
    VERIFICATION_FAIL,
    VERIFICATION_PASS,
    VerificationFinding,
    VerificationResult,
)
from models.workspace import Workspace
from services.environment_service import LOG_FILENAME as ENVIRONMENT_LOG_FILENAME
from services.environment_service import VENV_DIRNAME
from services.execution_service import LOG_FILENAME as EXECUTION_LOG_FILENAME
from workspace.manager import REPOSITORY_SUBDIRS

REQUIRED_REPOSITORY_FILES = ("README.md", "requirements.txt")
REQUIRED_GENERATED_FILES = ("scripts/train.py",)
EXPECTED_OUTPUT_FILES: tuple[str, ...] = ()


class VerificationService:
    def verify(
        self,
        workspace: Workspace,
        execution_result: ExecutionResult,
    ) -> VerificationResult:
        findings: list[VerificationFinding] = []

        repository_status = self._verify_repository(workspace, findings)
        environment_status = self._verify_environment(workspace, findings)
        execution_status = self._verify_execution(workspace, execution_result, findings)
        output_status = self._verify_outputs(workspace, findings)

        category_statuses = (
            repository_status,
            environment_status,
            execution_status,
            output_status,
        )
        overall_status = (
            VERIFICATION_PASS
            if all(status == VERIFICATION_PASS for status in category_statuses)
            else VERIFICATION_FAIL
        )

        return VerificationResult(
            repository_status=repository_status,
            environment_status=environment_status,
            execution_status=execution_status,
            output_status=output_status,
            overall_status=overall_status,
            findings=findings,
        )

    def _verify_repository(
        self,
        workspace: Workspace,
        findings: list[VerificationFinding],
    ) -> str:
        workspace_path = workspace.root_path.resolve()
        passed = True

        for subdir in REPOSITORY_SUBDIRS:
            path = workspace_path / subdir
            if not path.is_dir():
                passed = False
                findings.append(
                    VerificationFinding(
                        category="repository",
                        code="missing_directory",
                        message=f"Required directory missing: {subdir}/",
                    )
                )

        for relative_path in REQUIRED_REPOSITORY_FILES:
            path = workspace_path / relative_path
            if not path.is_file():
                passed = False
                findings.append(
                    VerificationFinding(
                        category="repository",
                        code="missing_file",
                        message=f"Required file missing: {relative_path}",
                    )
                )

        for relative_path in REQUIRED_GENERATED_FILES:
            path = workspace_path / relative_path
            if not path.is_file():
                passed = False
                findings.append(
                    VerificationFinding(
                        category="repository",
                        code="missing_generated_file",
                        message=f"Required generated file missing: {relative_path}",
                    )
                )

        return VERIFICATION_PASS if passed else VERIFICATION_FAIL

    def _verify_environment(
        self,
        workspace: Workspace,
        findings: list[VerificationFinding],
    ) -> str:
        workspace_path = workspace.root_path.resolve()
        passed = True

        venv_path = workspace_path / VENV_DIRNAME
        if not venv_path.is_dir():
            passed = False
            findings.append(
                VerificationFinding(
                    category="environment",
                    code="missing_virtual_environment",
                    message=f"Virtual environment missing: {VENV_DIRNAME}/",
                )
            )

        env_log_path = workspace_path / "logs" / ENVIRONMENT_LOG_FILENAME
        if not env_log_path.is_file():
            passed = False
            findings.append(
                VerificationFinding(
                    category="environment",
                    code="missing_environment_log",
                    message=f"Environment preparation log missing: logs/{ENVIRONMENT_LOG_FILENAME}",
                )
            )
        elif not self._environment_preparation_succeeded(env_log_path):
            passed = False
            findings.append(
                VerificationFinding(
                    category="environment",
                    code="environment_preparation_failed",
                    message="Environment preparation did not complete successfully",
                )
            )

        return VERIFICATION_PASS if passed else VERIFICATION_FAIL

    def _verify_execution(
        self,
        workspace: Workspace,
        execution_result: ExecutionResult,
        findings: list[VerificationFinding],
    ) -> str:
        workspace_path = workspace.root_path.resolve()
        passed = True

        execution_log_path = workspace_path / "logs" / EXECUTION_LOG_FILENAME
        if not execution_log_path.is_file():
            passed = False
            findings.append(
                VerificationFinding(
                    category="execution",
                    code="missing_execution_log",
                    message=f"Execution log missing: logs/{EXECUTION_LOG_FILENAME}",
                )
            )

        if execution_result.exit_code != 0:
            passed = False
            findings.append(
                VerificationFinding(
                    category="execution",
                    code="nonzero_exit_code",
                    message=(
                        f"Execution failed with exit code {execution_result.exit_code}"
                    ),
                )
            )

        if not execution_result.executed_command.strip():
            passed = False
            findings.append(
                VerificationFinding(
                    category="execution",
                    code="missing_executed_command",
                    message="Execution result does not record an executed command",
                )
            )

        return VERIFICATION_PASS if passed else VERIFICATION_FAIL

    def _verify_outputs(
        self,
        workspace: Workspace,
        findings: list[VerificationFinding],
    ) -> str:
        workspace_path = workspace.root_path.resolve()
        passed = True

        outputs_path = workspace_path / "outputs"
        if not outputs_path.is_dir():
            passed = False
            findings.append(
                VerificationFinding(
                    category="output",
                    code="missing_outputs_directory",
                    message="Outputs directory missing: outputs/",
                )
            )
            return VERIFICATION_FAIL

        for relative_path in EXPECTED_OUTPUT_FILES:
            path = workspace_path / "outputs" / relative_path
            if not path.is_file():
                passed = False
                findings.append(
                    VerificationFinding(
                        category="output",
                        code="missing_output_file",
                        message=f"Expected output file missing: outputs/{relative_path}",
                    )
                )

        return VERIFICATION_PASS if passed else VERIFICATION_FAIL

    @staticmethod
    def _environment_preparation_succeeded(log_path: Path) -> bool:
        content = log_path.read_text(encoding="utf-8")
        return "Status: SUCCESS" in content
