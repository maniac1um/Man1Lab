from typing import Any

from ports.output_format import OutputFormat


def export_docling_document(
    document: Any,
    output_format: OutputFormat,
) -> str:
    """Serialize a Docling document using the configured output format."""
    if output_format is OutputFormat.MARKDOWN:
        return document.export_to_markdown().strip()
    if output_format is OutputFormat.JSON:
        raise NotImplementedError(
            "OutputFormat.JSON is reserved for future Docling export support."
        )
    if output_format is OutputFormat.DOCTAGS:
        raise NotImplementedError(
            "OutputFormat.DOCTAGS is reserved for future Docling export support."
        )
    raise ValueError(f"Unsupported output format: {output_format!r}")
