import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.reader import Reader
from llm.mock_provider import MOCK_REPRODUCTION_ANALYSIS_JSON
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from adapters.pymupdf_parser import PyMuPDFParser
from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader
from tests.fixtures import create_sample_paper_pdf
from tests.support.prompt import default_prompt_builder


class ReaderPromptIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.paper_path = Path(self.temp_dir.name) / "sample.pdf"
        create_sample_paper_pdf(self.paper_path)

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)
        self.temp_dir.cleanup()

    def test_reader_prompt_targets_reproduction_analysis(self) -> None:
        prompt = PromptBuilder(PromptLoader()).build_reader_prompt()

        self.assertIn("Reproduction Information Extraction", prompt)
        self.assertIn("reproduction_gaps", prompt)
        self.assertIn("Never infer", prompt)
        self.assertIn("PaperReproductionAnalysis", prompt)
        self.assertIn("five reproduction questions", prompt.casefold())
        self.assertNotIn("If a field is missing, write \"Unknown\"", prompt)
        self.assertNotIn("- abstract\n", prompt)
        self.assertIn("OUTPUT", prompt.upper())

    def test_reader_run_returns_paper_reproduction_analysis(self) -> None:
        class RecordingLLM:
            def __init__(self) -> None:
                self.messages = None

            def complete(self, messages, *, temperature: float = 0.0) -> str:
                self.messages = messages
                return MOCK_REPRODUCTION_ANALYSIS_JSON

        llm = RecordingLLM()
        reader = Reader(document_parser=PyMuPDFParser(), prompt_builder=default_prompt_builder(), llm=llm)
        analysis = reader.run(self.paper_path)

        self.assertIsInstance(analysis, PaperReproductionAnalysis)
        self.assertEqual(analysis.schema_version, "1.0")
        self.assertIn("reproduction_gaps", reader.analysis_snapshot())
        self.assertIn("PaperReproductionAnalysis", llm.messages[0].content)
        self.assertIn("reproduction_gaps", reader._last_extracted)

    def test_reader_prompt_section_order_includes_output(self) -> None:
        prompt = PromptBuilder(PromptLoader()).build_reader_prompt()
        schema_index = prompt.index("Top-level shape")
        output_index = prompt.index("Output contract")
        self.assertLess(schema_index, output_index)


if __name__ == "__main__":
    unittest.main()
