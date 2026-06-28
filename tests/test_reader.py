import logging
import tempfile
import unittest
from pathlib import Path

from agents.reader import Reader
from services.pdf_service import PDFService
from tests.fixtures import create_sample_paper_pdf


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


if __name__ == "__main__":
    unittest.main()
