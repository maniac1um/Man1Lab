from pathlib import Path

from ports.parsed_document import ParsedDocument
from services.pdf_service import PDFService


class PyMuPDFParser:
    """Document parser backed by PyMuPDF plain-text extraction (legacy fallback)."""

    def __init__(self, pdf_service: PDFService | None = None) -> None:
        self._pdf_service = pdf_service or PDFService()

    def parse(self, paper_path: Path) -> ParsedDocument:
        text = self._pdf_service.extract(paper_path)
        return ParsedDocument(markdown=text)
