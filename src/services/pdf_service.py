import logging
import re
import time
from pathlib import Path

import fitz

from services.exceptions import (
    PDFEmptyError,
    PDFEncryptedError,
    PDFExtractionError,
    PDFNotFoundError,
)

logger = logging.getLogger(__name__)


class PDFService:
    def extract(self, pdf_path: Path) -> str:
        if not pdf_path.exists():
            raise PDFNotFoundError(f"PDF not found: {pdf_path}")

        start = time.perf_counter()
        document: fitz.Document | None = None

        try:
            document = fitz.open(pdf_path)
        except Exception as exc:
            raise PDFExtractionError(f"Failed to open PDF: {pdf_path}") from exc

        try:
            if document.is_encrypted and not document.authenticate(""):
                raise PDFEncryptedError(f"PDF is encrypted and cannot be read: {pdf_path}")

            page_texts = [page.get_text() for page in document]
            page_count = len(page_texts)
            text = self._normalize_whitespace("\n".join(page_texts))

            if not text:
                raise PDFEmptyError(f"PDF contains no extractable text: {pdf_path}")

            duration = time.perf_counter() - start
            logger.info(
                "PDF extraction complete: pages=%d chars=%d duration=%.3fs file=%s",
                page_count,
                len(text),
                duration,
                pdf_path.name,
            )
            return text
        except (PDFEmptyError, PDFEncryptedError):
            raise
        except Exception as exc:
            raise PDFExtractionError(
                f"Failed to extract text from PDF: {pdf_path}"
            ) from exc
        finally:
            if document is not None:
                document.close()

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines).strip()
