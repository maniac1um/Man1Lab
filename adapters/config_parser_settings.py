from configuration.provider import SettingsProvider, get_settings_provider
from ports.output_format import OutputFormat
from ports.parser_settings import ParserSettings, ParserSettingsProvider


class ConfigParserSettingsProvider:
    """Read parser settings from the application settings provider."""

    def __init__(self, settings_provider: SettingsProvider | None = None) -> None:
        self._settings_provider = settings_provider or get_settings_provider()

    def get_parser_settings(self) -> ParserSettings:
        settings = self._settings_provider.get_settings()
        return ParserSettings(
            backend=settings.parser.backend.strip().lower(),
            output_format=OutputFormat.MARKDOWN,
            max_paper_text_chars=settings.parser.max_paper_text_chars,
        )
