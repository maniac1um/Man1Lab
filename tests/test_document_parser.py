import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from adapters.docling_parser import DoclingParser
from adapters.factory import build_document_parser
from adapters.pymupdf_parser import PyMuPDFParser
from adapters.output_export import export_docling_document
from ports.output_format import OutputFormat
from ports.parser_settings import ParserSettings
from services.exceptions import PDFEmptyError, PDFNotFoundError
from tests.fixtures import create_sample_paper_pdf


class DocumentParserFactoryTest(unittest.TestCase):
    def test_build_docling_backend(self) -> None:
        settings = ParserSettings(backend="docling")
        parser = build_document_parser(settings=settings)
        self.assertIsInstance(parser, DoclingParser)

    def test_build_pymupdf_backend(self) -> None:
        settings = ParserSettings(backend="pymupdf")
        parser = build_document_parser(settings=settings)
        self.assertIsInstance(parser, PyMuPDFParser)

    def test_invalid_backend_raises(self) -> None:
        settings = ParserSettings(backend="unknown")
        with self.assertRaises(ValueError):
            build_document_parser(settings=settings)


class DoclingParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_missing_file_raises(self) -> None:
        parser = DoclingParser(converter=MagicMock())
        with self.assertRaises(PDFNotFoundError):
            parser.parse(self.base_path / "missing.pdf")

    def test_empty_markdown_raises(self) -> None:
        converter = MagicMock()
        converter.convert.return_value.document.export_to_markdown.return_value = "   "
        parser = DoclingParser(converter=converter)
        pdf_path = self.base_path / "paper.pdf"
        create_sample_paper_pdf(pdf_path)
        with self.assertRaises(PDFEmptyError):
            parser.parse(pdf_path)

    def test_returns_parsed_document_with_markdown(self) -> None:
        converter = MagicMock()
        converter.convert.return_value.document.export_to_markdown.return_value = (
            "## Title\n\nAbstract content."
        )
        converter.convert.return_value.status = "SUCCESS"
        parser = DoclingParser(converter=converter)
        pdf_path = self.base_path / "paper.pdf"
        create_sample_paper_pdf(pdf_path)
        parsed = parser.parse(pdf_path)
        self.assertIn("## Title", parsed.markdown)
        self.assertIsNone(parsed.sections)
        converter.convert.assert_called_once_with(str(pdf_path))


class OutputExportTest(unittest.TestCase):
    def test_markdown_export(self) -> None:
        document = MagicMock()
        document.export_to_markdown.return_value = "  ## Section  \n"
        text = export_docling_document(document, OutputFormat.MARKDOWN)
        self.assertEqual(text, "## Section")

    def test_json_export_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            export_docling_document(MagicMock(), OutputFormat.JSON)

    def test_doctags_export_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            export_docling_document(MagicMock(), OutputFormat.DOCTAGS)


if __name__ == "__main__":
    unittest.main()
