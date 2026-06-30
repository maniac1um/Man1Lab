from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedDocument:
    """Structured output of document parsing for downstream Paper Analysis.

    Only ``markdown`` is populated today. Additional fields are reserved so
    adapters can expose richer Docling exports without changing ``DocumentParser``.
    """

    markdown: str

    # Reserved — not populated by current adapters.
    metadata: dict[str, Any] | None = None
    sections: list[Any] | None = None
    figures: list[Any] | None = None
    tables: list[Any] | None = None
    equations: list[Any] | None = None
    references: list[Any] | None = None
