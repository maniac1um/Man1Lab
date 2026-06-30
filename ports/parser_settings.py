from dataclasses import dataclass
from typing import Protocol

from ports.output_format import OutputFormat


@dataclass(frozen=True)
class ParserSettings:
    """Configuration for document parser construction and export behavior."""

    backend: str
    output_format: OutputFormat = OutputFormat.MARKDOWN
    max_paper_text_chars: int = 80_000


class ParserSettingsProvider(Protocol):
    """Supply parser settings without binding the factory to a config module."""

    def get_parser_settings(self) -> ParserSettings: ...
