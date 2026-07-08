import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.planner import Planner
from llm.mock_provider import MOCK_PLANNER_JSON
from tests.fixtures import sample_reproduction_analysis
from validation.exceptions import TaskValidationError
from tests.support.prompt import default_prompt_builder


class FakePromptBuilder:
    def build_planner_prompt(self) -> str:
        return "PLANNER SYSTEM PROMPT"


class FakeLLMProvider:
    def __init__(self, response: str = MOCK_PLANNER_JSON) -> None:
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
        return {
            "paper_title": "Test Paper",
            "tasks": [
                {
                    "id": "task_1",
                    "name": "Environment setup",
                    "description": "Set up environment.",
                    "depends_on": [],
                }
            ],
        }


def _sample_analysis():
    return sample_reproduction_analysis(source_path=Path("paper.pdf"))


class InvalidDependencyParser:
    def parse(self, raw_response: str) -> dict:
        return {
            "paper_title": "Test Paper",
            "tasks": [
                {
                    "id": "task_1",
                    "name": "Step A",
                    "description": "Do A.",
                    "depends_on": ["missing_task"],
                }
            ],
        }


class PlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)

    def test_planner_invokes_prompt_builder(self) -> None:
        builder = FakePromptBuilder()
        llm = FakeLLMProvider()
        planner = Planner(prompt_builder=builder, llm=llm)
        planner.run_legacy(_sample_analysis())
        self.assertEqual(planner._last_prompt, "PLANNER SYSTEM PROMPT")

    def test_planner_invokes_llm_and_response_parser(self) -> None:
        llm = FakeLLMProvider()
        parser = FakeResponseParser()
        planner = Planner(
            prompt_builder=FakePromptBuilder(),
            llm=llm,
            response_parser=parser,
        )
        task = planner.run_legacy(_sample_analysis())

        self.assertTrue(llm.complete_called)
        self.assertIn("Goal:", llm.messages[1].content)
        self.assertIn("Reproduction gaps:", llm.messages[1].content)
        self.assertNotIn('"abstract"', llm.messages[1].content)
        self.assertTrue(parser.parse_called)
        self.assertEqual(planner._last_extracted["paper_title"], "Test Paper")
        self.assertEqual(len(planner._last_extracted["tasks"]), 1)
        self.assertEqual(task.paper_title, "Test Paper")
        self.assertEqual(len(task.steps), 1)
        self.assertEqual(task.steps[0].id, "task_1")
        self.assertEqual(task.steps[0].name, "Environment setup")

    def test_planner_validation_failure_raises(self) -> None:
        planner = Planner(
            prompt_builder=FakePromptBuilder(),
            llm=FakeLLMProvider(),
            response_parser=InvalidDependencyParser(),
        )
        with self.assertRaises(TaskValidationError):
            planner.run_legacy(_sample_analysis())

    def test_planner_produces_structured_task_dict_with_mock_llm(self) -> None:
        planner = Planner(prompt_builder=default_prompt_builder())
        planner.run_legacy(_sample_analysis())
        extracted = planner._last_extracted

        self.assertEqual(
            extracted["paper_title"],
            "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion",
        )
        self.assertGreater(len(extracted["tasks"]), 0)
        first_task = extracted["tasks"][0]
        self.assertIn("id", first_task)
        self.assertIn("name", first_task)
        self.assertIn("description", first_task)
        self.assertIn("depends_on", first_task)

    def test_planner_does_not_access_prompt_files_directly(self) -> None:
        planner = Planner(
            prompt_builder=FakePromptBuilder(),
            llm=FakeLLMProvider(),
        )
        with patch("pathlib.Path.read_text") as read_text:
            planner.run_legacy(_sample_analysis())
            read_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
