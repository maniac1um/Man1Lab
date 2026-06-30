import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.reader import Reader
from llm.mock_provider import MOCK_REPRODUCTION_ANALYSIS_JSON
from models.paper_reproduction_analysis import PaperReproductionAnalysis, ReproductionScope
from adapters.pymupdf_parser import PyMuPDFParser
from tests.fixtures import create_sample_paper_pdf
from validation.exceptions import AnalysisValidationError


class FakePromptBuilder:
    def __init__(self) -> None:
        self.build_called = False

    def build_reader_prompt(self) -> str:
        self.build_called = True
        return "SYSTEM\n\nEXTRACTION"


class FakeLLMProvider:
    def __init__(self, response: str = MOCK_REPRODUCTION_ANALYSIS_JSON) -> None:
        self.complete_called = False
        self.messages = None
        self._response = response

    def complete(self, messages, *, temperature: float = 0.0) -> str:
        self.complete_called = True
        self.messages = messages
        return self._response


class FakeResponseParser:
    def __init__(self, data: dict | None = None) -> None:
        self.parse_called = False
        self.raw_input = None
        self._data = data or {
            "metadata": {"title": "Parsed Title"},
            "goal": {"research_goal": "Parsed reproduction goal."},
        }

    def parse(self, raw_response: str) -> dict:
        self.parse_called = True
        self.raw_input = raw_response
        return dict(self._data)


class ReaderTest(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.paper_path = Path(self.temp_dir.name) / "sample.pdf"
        create_sample_paper_pdf(self.paper_path)
        self.reader = Reader(document_parser=PyMuPDFParser())

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)
        self.temp_dir.cleanup()

    def test_reader_returns_extracted_text(self) -> None:
        text = self.reader.read_text(self.paper_path)
        self.assertIsInstance(text, str)
        self.assertIn("Diffusion Policy", text)
        self.assertGreater(len(text), 0)

    def test_reader_uses_prompt_builder(self) -> None:
        builder = FakePromptBuilder()
        llm = FakeLLMProvider()
        reader = Reader(
            document_parser=PyMuPDFParser(),
            prompt_builder=builder,
            llm=llm,
        )
        reader.run(self.paper_path)
        self.assertTrue(builder.build_called)
        self.assertEqual(reader._last_prompt, "SYSTEM\n\nEXTRACTION")

    def test_reader_does_not_access_prompt_files_directly(self) -> None:
        builder = FakePromptBuilder()
        llm = FakeLLMProvider()
        reader = Reader(
            document_parser=PyMuPDFParser(),
            prompt_builder=builder,
            llm=llm,
        )
        with patch("pathlib.Path.read_text") as read_text:
            reader.run(self.paper_path)
            read_text.assert_not_called()

    def test_run_returns_paper_reproduction_analysis(self) -> None:
        llm = FakeLLMProvider()
        parser = FakeResponseParser(
            {
                "metadata": {"title": "From LLM"},
                "goal": {"research_goal": "Parsed reproduction goal."},
            }
        )
        reader = Reader(
            document_parser=PyMuPDFParser(),
            prompt_builder=FakePromptBuilder(),
            llm=llm,
            response_parser=parser,
        )
        analysis = reader.run(self.paper_path)

        self.assertTrue(llm.complete_called)
        self.assertTrue(parser.parse_called)
        self.assertIsInstance(analysis, PaperReproductionAnalysis)
        self.assertEqual(analysis.metadata.title, "From LLM")
        self.assertEqual(analysis.goal.research_goal, "Parsed reproduction goal.")
        self.assertEqual(analysis.metadata.source_path, self.paper_path)
        self.assertEqual(reader.last_analysis, analysis)

    def test_reader_validation_failure_raises(self) -> None:
        parser = FakeResponseParser({"goal": {"research_goal": "No title field."}})
        reader = Reader(
            document_parser=PyMuPDFParser(),
            prompt_builder=FakePromptBuilder(),
            llm=FakeLLMProvider(),
            response_parser=parser,
        )
        with self.assertRaises(AnalysisValidationError):
            reader.run(self.paper_path)

    def test_analysis_snapshot_round_trip(self) -> None:
        reader = Reader(
            document_parser=PyMuPDFParser(),
            prompt_builder=FakePromptBuilder(),
            llm=FakeLLMProvider(),
        )
        reader.run(self.paper_path)
        snapshot = reader.analysis_snapshot()
        self.assertIsNotNone(snapshot)
        restored = PaperReproductionAnalysis.model_validate(snapshot)
        self.assertEqual(restored.metadata.title, reader.last_analysis.metadata.title)

    def test_save_analysis_snapshot_writes_file(self) -> None:
        reader = Reader(
            document_parser=PyMuPDFParser(),
            prompt_builder=FakePromptBuilder(),
            llm=FakeLLMProvider(),
        )
        reader.run(self.paper_path)
        snapshot_path = Path(self.temp_dir.name) / "analysis_snapshot.json"
        reader.save_analysis_snapshot(snapshot_path)
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["metadata"]["title"], reader.last_analysis.metadata.title)

    def test_mock_llm_native_analysis_shape(self) -> None:
        reader = Reader(
            document_parser=PyMuPDFParser(),
            prompt_builder=FakePromptBuilder(),
            llm=FakeLLMProvider(),
        )
        analysis = reader.run(self.paper_path)
        self.assertEqual(analysis.goal.scope, ReproductionScope.FULL_REPRODUCTION)
        self.assertEqual(analysis.method.framework, "PyTorch")
        self.assertEqual(analysis.resources.datasets[0].name, "Robomimic benchmark tasks")


if __name__ == "__main__":
    unittest.main()
