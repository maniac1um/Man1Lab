import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.coder import Coder
from agents.planner import Planner
from agents.reader import Reader
from agents.reporter import Reporter
from agents.reviewer import Reviewer
from agents.runner import Runner
from llm.mock_provider import (
    MOCK_PATCH_ITERATION_JSON,
    MOCK_PATCH_NO_ITERATION_JSON,
    MOCK_REVIEWER_FAIL_JSON,
    MOCK_REVIEWER_PASS_JSON,
    MockLLMProvider,
)
from models.review import PatchPlan
from models.review_report import ReviewReport
from planning.patch_planner import PatchPlanner
from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader
from services.environment_service import EnvironmentService
from services.execution_service import ExecutionService
from services.pdf_service import PDFService
from tests.fixtures import create_sample_paper_pdf
from tests.runner_mocks import failing_train_command_runner, mock_command_runner
from validation.exceptions import PatchValidationError
from validation.patch import build_patch_plan
from validation.review import build_review_report
from workflow.orchestrator import WorkflowOrchestrator
from workspace.manager import WorkspaceManager


_VALID_PATCH_DATA = {
    "requires_patch": False,
    "priority": "low",
    "targets": [],
    "reason": "Verification passed.",
    "strategy": "Proceed to reporting.",
}


class PatchPlanValidationTest(unittest.TestCase):
    def test_build_patch_plan_success(self) -> None:
        plan = build_patch_plan(_VALID_PATCH_DATA)
        self.assertIsInstance(plan, PatchPlan)
        self.assertFalse(plan.requires_patch)
        self.assertEqual(plan.priority, "LOW")

    def test_missing_required_field_raises(self) -> None:
        data = dict(_VALID_PATCH_DATA)
        del data["reason"]
        with self.assertRaises(PatchValidationError):
            build_patch_plan(data)

    def test_invalid_priority_raises(self) -> None:
        data = dict(_VALID_PATCH_DATA)
        data["priority"] = "CRITICAL"
        with self.assertRaises(PatchValidationError):
            build_patch_plan(data)

    def test_invalid_targets_raises(self) -> None:
        data = dict(_VALID_PATCH_DATA)
        data["targets"] = ["valid", ""]
        with self.assertRaises(PatchValidationError):
            build_patch_plan(data)


class FakePromptBuilder:
    def build_patch_planner_prompt(self) -> str:
        return "PATCH PLANNER PROMPT"


class FakeLLMProvider:
    def __init__(self, response: str = MOCK_PATCH_NO_ITERATION_JSON) -> None:
        self.complete_called = False
        self.messages = None
        self._response = response

    def complete(self, messages, *, temperature: float = 0.0) -> str:
        self.complete_called = True
        self.messages = messages
        return self._response


class PatchPlannerTest(unittest.TestCase):
    def test_plan_without_iteration(self) -> None:
        review_report = build_review_report(json.loads(MOCK_REVIEWER_PASS_JSON))
        planner = PatchPlanner(
            prompt_builder=FakePromptBuilder(),
            llm=FakeLLMProvider(MOCK_PATCH_NO_ITERATION_JSON),
        )

        plan = planner.plan(review_report)

        self.assertFalse(plan.requires_patch)
        self.assertEqual(plan.priority, "LOW")

    def test_plan_with_iteration(self) -> None:
        review_report = build_review_report(json.loads(MOCK_REVIEWER_FAIL_JSON))
        planner = PatchPlanner(
            prompt_builder=FakePromptBuilder(),
            llm=FakeLLMProvider(MOCK_PATCH_ITERATION_JSON),
        )

        plan = planner.plan(review_report)

        self.assertTrue(plan.requires_patch)
        self.assertEqual(plan.targets, ["execution"])


class ReviewerPatchPlannerIntegrationTest(unittest.TestCase):
    def test_reviewer_to_patch_planner_flow(self) -> None:
        reviewer = Reviewer(
            llm=MockLLMProvider(MOCK_REVIEWER_PASS_JSON),
            patch_planner=PatchPlanner(
                llm=MockLLMProvider(MOCK_PATCH_NO_ITERATION_JSON),
            ),
        )
        from models.paper import PaperModel
        from models.task import TaskModel, TaskStep
        from models.verification import VERIFICATION_PASS, VerificationResult

        paper = PaperModel(
            title="Paper",
            abstract="",
            method="",
            dataset="",
            model="",
            framework="",
            optimizer="",
            loss="",
            training_pipeline="",
            evaluation_metric="",
            source_path=Path("paper.pdf"),
        )
        task = TaskModel(
            paper_title="Paper",
            steps=[TaskStep(id="task_1", name="Train", description="Train.")],
        )
        verification = VerificationResult(
            repository_status=VERIFICATION_PASS,
            environment_status=VERIFICATION_PASS,
            execution_status=VERIFICATION_PASS,
            output_status=VERIFICATION_PASS,
            overall_status=VERIFICATION_PASS,
        )

        review_report = reviewer.run(paper, task, verification)
        patch_plan = reviewer.plan_patch(review_report)

        self.assertFalse(patch_plan.requires_patch)


class PromptBuilderPatchPlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prompts_dir = Path(self.temp_dir.name)
        patch_dir = self.prompts_dir / "patch_planner"
        patch_dir.mkdir(parents=True)
        (patch_dir / "system.md").write_text("PSYSTEM", encoding="utf-8")
        (patch_dir / "extraction.md").write_text("PEXTRACTION", encoding="utf-8")
        (patch_dir / "schema.md").write_text("PSCHEMA", encoding="utf-8")
        (patch_dir / "examples.md").write_text("PEXAMPLES", encoding="utf-8")
        self.builder = PromptBuilder(PromptLoader(prompts_dir=self.prompts_dir))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_build_patch_planner_prompt_combines_sections(self) -> None:
        prompt = self.builder.build_patch_planner_prompt()
        self.assertLess(prompt.index("PSYSTEM"), prompt.index("PEXTRACTION"))
        self.assertLess(prompt.index("PEXTRACTION"), prompt.index("PSCHEMA"))
        self.assertLess(prompt.index("PSCHEMA"), prompt.index("PEXAMPLES"))


class PatchWorkflowBranchTest(unittest.TestCase):
    def _run_workflow(self, *, patch_json: str, failing_runner: bool = False) -> list:
        captured_history: list = []

        class CapturingReporter(Reporter):
            def run(self, history):
                captured_history.append(history)
                return super().run(history)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            paper_path = temp_path / "paper.pdf"
            create_sample_paper_pdf(paper_path)
            workspace_manager = WorkspaceManager(
                root=temp_path / "workspace/tasks",
                outputs_dir=temp_path / "outputs",
            )
            train_runner = (
                failing_train_command_runner
                if failing_runner
                else mock_command_runner
            )
            orchestrator = WorkflowOrchestrator(
                reader=Reader(pdf_service=PDFService()),
                planner=Planner(),
                coder=Coder(workspace_manager=workspace_manager),
                runner=Runner(
                    environment_service=EnvironmentService(
                        command_runner=mock_command_runner
                    ),
                    execution_service=ExecutionService(
                        command_runner=train_runner
                    ),
                ),
                reviewer=Reviewer(
                    llm=MockLLMProvider(
                        MOCK_REVIEWER_FAIL_JSON if failing_runner else MOCK_REVIEWER_PASS_JSON
                    ),
                ),
                reporter=CapturingReporter(),
                workspace_manager=workspace_manager,
                patch_planner=PatchPlanner(llm=MockLLMProvider(patch_json)),
            )
            orchestrator.run(paper_path)
        return captured_history

    def test_requires_patch_false_branch(self) -> None:
        history = self._run_workflow(patch_json=MOCK_PATCH_NO_ITERATION_JSON)[0]
        self.assertEqual(len(history.patch_plans), 1)
        self.assertFalse(history.patch_plans[0].requires_patch)
        self.assertEqual(len(history.execution_results), 1)

    def test_requires_patch_true_branch_without_rerun(self) -> None:
        history = self._run_workflow(
            patch_json=MOCK_PATCH_ITERATION_JSON,
            failing_runner=True,
        )[0]
        self.assertEqual(len(history.patch_plans), 1)
        self.assertTrue(history.patch_plans[0].requires_patch)
        self.assertEqual(len(history.execution_results), 1)

    def test_no_infinite_loop_when_iteration_required(self) -> None:
        with patch("config.MAX_REVIEW_ITERATIONS", 3):
            history = self._run_workflow(
                patch_json=MOCK_PATCH_ITERATION_JSON,
                failing_runner=True,
            )[0]
        self.assertEqual(len(history.patch_plans), 1)
        self.assertEqual(len(history.execution_results), 1)


if __name__ == "__main__":
    unittest.main()
