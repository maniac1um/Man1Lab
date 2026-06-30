from pathlib import Path
from typing import Protocol

from ports.parsed_document import ParsedDocument


class DocumentParser(Protocol):
    """Parse a research paper file into a structured document for Paper Analysis."""

    def parse(self, paper_path: Path) -> ParsedDocument:
        """Return parsed document content suitable for LLM paper analysis."""
