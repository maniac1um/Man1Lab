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


class EnvironmentError(Exception):
    """Base exception for environment preparation errors."""


class RequirementsNotFoundError(EnvironmentError):
    """Raised when requirements.txt is missing from the workspace."""


class ExecutionPlanError(Exception):
    """Raised when an execution plan cannot be built for the workspace."""
