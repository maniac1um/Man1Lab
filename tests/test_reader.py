import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.reader import Reader
from llm.mock_provider import MOCK_PAPER_JSON
from services.pdf_service import PDFService
from tests.fixtures import create_sample_paper_pdf
from validation.exceptions import PaperValidationError


class FakePromptBuilder:
    def __init__(self) -> None:
        self.build_called = False

    def build_reader_prompt(self) -> str:
        self.build_called = True
        return "SYSTEM\n\nEXTRACTION"


class FakeLLMProvider:
    def __init__(self, response: str = MOCK_PAPER_JSON) -> None:
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
        self._data = data or {"title": "Parsed Title"}

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
        self.reader = Reader(pdf_service=PDFService())

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
            pdf_service=PDFService(),
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
            pdf_service=PDFService(),
            prompt_builder=builder,
            llm=llm,
        )
        with patch("pathlib.Path.read_text") as read_text:
            reader.run(self.paper_path)
            read_text.assert_not_called()

    def test_reader_invokes_llm_and_response_parser(self) -> None:
        llm = FakeLLMProvider(response='{"title": "From LLM"}')
        parser = FakeResponseParser({"title": "From LLM", "abstract": "Parsed abstract."})
        reader = Reader(
            pdf_service=PDFService(),
            prompt_builder=FakePromptBuilder(),
            llm=llm,
            response_parser=parser,
        )
        paper = reader.run(self.paper_path)

        self.assertTrue(llm.complete_called)
        self.assertTrue(parser.parse_called)
        self.assertEqual(reader._last_extracted, {"title": "From LLM", "abstract": "Parsed abstract."})
        self.assertEqual(paper.title, "From LLM")
        self.assertEqual(paper.abstract, "Parsed abstract.")

    def test_reader_validation_failure_raises(self) -> None:
        parser = FakeResponseParser({"abstract": "No title field."})
        reader = Reader(
            pdf_service=PDFService(),
            prompt_builder=FakePromptBuilder(),
            llm=FakeLLMProvider(),
            response_parser=parser,
        )
        with self.assertRaises(PaperValidationError):
            reader.run(self.paper_path)


if __name__ == "__main__":
    unittest.main()
