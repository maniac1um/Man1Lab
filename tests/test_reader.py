import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.reader import Reader
from services.pdf_service import PDFService
from tests.fixtures import create_sample_paper_pdf


class FakePromptBuilder:
    def __init__(self) -> None:
        self.build_called = False

    def build_reader_prompt(self) -> str:
        self.build_called = True
        return "SYSTEM\n\nEXTRACTION"


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
        reader = Reader(pdf_service=PDFService(), prompt_builder=builder)
        reader.run(self.paper_path)
        self.assertTrue(builder.build_called)
        self.assertEqual(reader._last_prompt, "SYSTEM\n\nEXTRACTION")

    def test_reader_does_not_access_prompt_files_directly(self) -> None:
        builder = FakePromptBuilder()
        reader = Reader(pdf_service=PDFService(), prompt_builder=builder)
        with patch("pathlib.Path.read_text") as read_text:
            reader.run(self.paper_path)
            read_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
