from enum import Enum


class OutputFormat(str, Enum):
    """Target serialization for adapter document export."""

    MARKDOWN = "markdown"
    JSON = "json"
    DOCTAGS = "doctags"
