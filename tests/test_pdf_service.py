import logging
import tempfile
import unittest
from pathlib import Path

from services.exceptions import PDFEmptyError, PDFEncryptedError, PDFNotFoundError
from services.pdf_service import PDFService
from tests.fixtures import (
    create_empty_paper_pdf,
    create_encrypted_paper_pdf,
    create_sample_paper_pdf,
)


class PDFServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.service = PDFService()

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)
        self.temp_dir.cleanup()

    def test_extract_normal_pdf(self) -> None:
        pdf_path = self.base_path / "normal.pdf"
        create_sample_paper_pdf(pdf_path)

        text = self.service.extract(pdf_path)

        self.assertIn("Diffusion Policy", text)
        self.assertIn("Abstract:", text)

    def test_extract_missing_file_raises(self) -> None:
        missing_path = self.base_path / "missing.pdf"
        with self.assertRaises(PDFNotFoundError):
            self.service.extract(missing_path)

    def test_extract_empty_pdf_raises(self) -> None:
        pdf_path = self.base_path / "empty.pdf"
        create_empty_paper_pdf(pdf_path)
        with self.assertRaises(PDFEmptyError):
            self.service.extract(pdf_path)

    def test_extract_encrypted_pdf_raises(self) -> None:
        pdf_path = self.base_path / "encrypted.pdf"
        create_encrypted_paper_pdf(pdf_path)
        with self.assertRaises(PDFEncryptedError):
            self.service.extract(pdf_path)


if __name__ == "__main__":
    unittest.main()
