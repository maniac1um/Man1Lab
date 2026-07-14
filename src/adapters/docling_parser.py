import logging
import time
from pathlib import Path

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from adapters.output_export import export_docling_document
from ports.output_format import OutputFormat
from ports.parsed_document import ParsedDocument
from services.exceptions import (
    PDFEmptyError,
    PDFEncryptedError,
    PDFExtractionError,
    PDFNotFoundError,
)

logger = logging.getLogger(__name__)


class DoclingParser:
    """Document parser backed by Docling structured document export."""

    def __init__(
        self,
        converter: DocumentConverter | None = None,
        *,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        max_paper_text_chars: int = 80_000,
    ) -> None:
        self._converter = converter or _build_converter()
        self._output_format = output_format
        self._max_paper_text_chars = max_paper_text_chars

    def parse(self, paper_path: Path) -> ParsedDocument:
        if not paper_path.exists():
            raise PDFNotFoundError(f"PDF not found: {paper_path}")

        start = time.perf_counter()
        try:
            result = self._converter.convert(str(paper_path))
        except Exception as exc:
            message = str(exc).lower()
            if "encrypt" in message or "password" in message:
                raise PDFEncryptedError(
                    f"PDF is encrypted and cannot be read: {paper_path}"
                ) from exc
            raise PDFExtractionError(
                f"Failed to parse PDF with Docling: {paper_path}"
            ) from exc

        markdown = export_docling_document(
            result.document,
            self._output_format,
        )
        if not markdown:
            raise PDFEmptyError(f"PDF contains no extractable text: {paper_path}")

        if self._max_paper_text_chars and len(markdown) > self._max_paper_text_chars:
            markdown = markdown[: self._max_paper_text_chars]

        duration = time.perf_counter() - start
        logger.info(
            "Docling parse complete: chars=%d duration=%.3fs file=%s status=%s format=%s",
            len(markdown),
            duration,
            paper_path.name,
            getattr(result, "status", "unknown"),
            self._output_format.value,
        )
        return ParsedDocument(markdown=markdown)


def _build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(
        do_ocr=False,
        do_table_structure=True,
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )
