from adapters.config_parser_settings import ConfigParserSettingsProvider
from adapters.docling_parser import DoclingParser
from adapters.pymupdf_parser import PyMuPDFParser
from ports.document_parser import DocumentParser
from ports.parser_settings import ParserSettings, ParserSettingsProvider

_SUPPORTED_BACKENDS = frozenset({"docling", "pymupdf"})


def build_document_parser(
    settings: ParserSettings | None = None,
    settings_provider: ParserSettingsProvider | None = None,
) -> DocumentParser:
    """Construct a document parser from explicit or provider-supplied settings."""
    if settings is None:
        provider = settings_provider or ConfigParserSettingsProvider()
        settings = provider.get_parser_settings()

    backend = settings.backend.strip().lower()
    if backend not in _SUPPORTED_BACKENDS:
        supported = ", ".join(sorted(_SUPPORTED_BACKENDS))
        raise ValueError(
            f"Unsupported parser backend={settings.backend!r}. "
            f"Expected one of: {supported}"
        )
    if backend == "pymupdf":
        return PyMuPDFParser()
    return DoclingParser(
        output_format=settings.output_format,
        max_paper_text_chars=settings.max_paper_text_chars,
    )
