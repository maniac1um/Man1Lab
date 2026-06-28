import json
import logging
import tempfile
import unittest
from pathlib import Path

from agents.reviewer import Reviewer
from llm.mock_provider import MOCK_REVIEWER_FAIL_JSON, MOCK_REVIEWER_PASS_JSON
from models.paper import PaperModel
from models.review_report import ReviewReport
from models.task import TaskModel, TaskStep
from models.verification import (
    VERIFICATION_FAIL,
    VERIFICATION_PASS,
    VerificationFinding,
    VerificationResult,
)
from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader
from validation.exceptions import ReviewValidationError
from validation.review import build_review_report


class FakePromptBuilder:
    def build_reviewer_prompt(self) -> str:
        return "REVIEWER SYSTEM PROMPT"


class FakeLLMProvider:
    def __init__(self, response: str = MOCK_REVIEWER_PASS_JSON) -> None:
        self.complete_called = False
        self.messages = None
        self._response = response

    def complete(self, messages, *, temperature: float = 0.0) -> str:
        self.complete_called = True
        self.messages = messages
        return self._response


class FakeResponseParser:
    def __init__(self) -> None:
        self.parse_called = False
        self.raw_input = None

    def parse(self, raw_response: str) -> dict:
        self.parse_called = True
        self.raw_input = raw_response
        return json.loads(MOCK_REVIEWER_PASS_JSON)


def _sample_paper() -> PaperModel:
    return PaperModel(
        title="Diffusion Policy",
        abstract="Abstract.",
        method="Method.",
        dataset="Dataset.",
        model="Model.",
        framework="PyTorch",
        optimizer="AdamW",
        loss="Loss.",
        training_pipeline="Pipeline.",
        evaluation_metric="Metric.",
        source_path=Path("paper.pdf"),
    )


def _sample_task() -> TaskModel:
    return TaskModel(
        paper_title="Diffusion Policy",
        steps=[
            TaskStep(
                id="task_1",
                name="Training",
                description="Train the model.",
            )
        ],
    )


def _pass_verification() -> VerificationResult:
    return VerificationResult(
        repository_status=VERIFICATION_PASS,
        environment_status=VERIFICATION_PASS,
        execution_status=VERIFICATION_PASS,
        output_status=VERIFICATION_PASS,
        overall_status=VERIFICATION_PASS,
        findings=[],
    )


def _fail_verification() -> VerificationResult:
    return VerificationResult(
        repository_status=VERIFICATION_PASS,
        environment_status=VERIFICATION_PASS,
        execution_status=VERIFICATION_FAIL,
        output_status=VERIFICATION_PASS,
        overall_status=VERIFICATION_FAIL,
        findings=[
            VerificationFinding(
                category="execution",
                code="nonzero_exit_code",
                message="Execution failed with exit code 1",
            )
        ],
    )


_VALID_REVIEW_DATA = {
    "summary": "Verification passed.",
    "analysis": "All categories passed.",
    "identified_issues": [],
    "strengths": ["Execution completed successfully."],
    "risk_level": "low",
    "next_action": "Continue reproduction assessment.",
}


class ReviewReportValidationTest(unittest.TestCase):
    def test_build_review_report_success(self) -> None:
        report = build_review_report(_VALID_REVIEW_DATA)
        self.assertIsInstance(report, ReviewReport)
        self.assertEqual(report.summary, "Verification passed.")
        self.assertEqual(report.risk_level, "LOW")
        self.assertEqual(report.identified_issues, [])

    def test_missing_required_field_raises(self) -> None:
        data = dict(_VALID_REVIEW_DATA)
        del data["summary"]
        with self.assertRaises(ReviewValidationError):
            build_review_report(data)

    def test_invalid_risk_level_raises(self) -> None:
        data = dict(_VALID_REVIEW_DATA)
        data["risk_level"] = "CRITICAL"
        with self.assertRaises(ReviewValidationError):
            build_review_report(data)

    def test_invalid_identified_issues_raises(self) -> None:
        data = dict(_VALID_REVIEW_DATA)
        data["identified_issues"] = ["valid", ""]
        with self.assertRaises(ReviewValidationError):
            build_review_report(data)


class ReviewerIntegrationTest(unittest.TestCase):
    def test_successful_review(self) -> None:
        llm = FakeLLMProvider(MOCK_REVIEWER_PASS_JSON)
        parser = FakeResponseParser()
        reviewer = Reviewer(
            prompt_builder=FakePromptBuilder(),
            llm=llm,
            response_parser=parser,
        )

        report = reviewer.run(_sample_paper(), _sample_task(), _pass_verification())

        self.assertTrue(llm.complete_called)
        self.assertTrue(parser.parse_called)
        self.assertEqual(report.risk_level, "LOW")
        self.assertEqual(report.identified_issues, [])
        self.assertIn("VerificationResult", llm.messages[1].content)

    def test_failed_verification_review(self) -> None:
        reviewer = Reviewer(
            prompt_builder=FakePromptBuilder(),
            llm=FakeLLMProvider(MOCK_REVIEWER_FAIL_JSON),
        )

        report = reviewer.run(_sample_paper(), _sample_task(), _fail_verification())

        self.assertEqual(report.risk_level, "HIGH")
        self.assertTrue(report.identified_issues)

    def test_user_message_contains_ground_truth_only_context(self) -> None:
        llm = FakeLLMProvider()
        reviewer = Reviewer(prompt_builder=FakePromptBuilder(), llm=llm)

        reviewer.run(_sample_paper(), _sample_task(), _pass_verification())

        user_message = llm.messages[1].content
        self.assertIn("VerificationResult (ground truth)", user_message)
        self.assertIn("overall_status", user_message)
        self.assertNotIn("workspace", user_message.lower())


class PromptBuilderReviewerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prompts_dir = Path(self.temp_dir.name)
        reviewer_dir = self.prompts_dir / "reviewer"
        reviewer_dir.mkdir(parents=True)
        (reviewer_dir / "system.md").write_text("RSYSTEM", encoding="utf-8")
        (reviewer_dir / "extraction.md").write_text("REXTRACTION", encoding="utf-8")
        (reviewer_dir / "schema.md").write_text("RSCHEMA", encoding="utf-8")
        (reviewer_dir / "examples.md").write_text("REXAMPLES", encoding="utf-8")
        self.builder = PromptBuilder(PromptLoader(prompts_dir=self.prompts_dir))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_build_reviewer_prompt_combines_sections_in_order(self) -> None:
        prompt = self.builder.build_reviewer_prompt()
        self.assertLess(prompt.index("RSYSTEM"), prompt.index("REXTRACTION"))
        self.assertLess(prompt.index("REXTRACTION"), prompt.index("RSCHEMA"))
        self.assertLess(prompt.index("RSCHEMA"), prompt.index("REXAMPLES"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
