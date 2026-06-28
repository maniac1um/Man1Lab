class PDFError(Exception):
    """Base exception for PDF ingestion errors."""


class PDFNotFoundError(PDFError):
    """Raised when the PDF file does not exist."""


class PDFEmptyError(PDFError):
    """Raised when the PDF contains no extractable text."""


class PDFEncryptedError(PDFError):
    """Raised when the PDF is encrypted and cannot be read."""


class PDFExtractionError(PDFError):
    """Raised when text extraction fails for any other reason."""
