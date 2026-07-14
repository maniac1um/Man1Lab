"""Legacy configuration facade.

Module-level constants are populated from ``LegacySettingsProvider`` on import.
``initialize_app_configuration()`` replaces them with Hydra-composed settings.
"""

from __future__ import annotations

from configuration.legacy_provider import LegacySettingsProvider
from configuration.models import AppSettings

WORKSPACE_ROOT = None  # type: ignore[assignment]
OUTPUTS_DIR = None  # type: ignore[assignment]
LOGS_DIR = None  # type: ignore[assignment]
PROMPTS_DIR = None  # type: ignore[assignment]
MAX_REVIEW_ITERATIONS = None  # type: ignore[assignment]
OPENAI_API_KEY = None  # type: ignore[assignment]
OPENAI_BASE_URL = None  # type: ignore[assignment]
OPENAI_MODEL = None  # type: ignore[assignment]
ANTHROPIC_API_KEY = None  # type: ignore[assignment]
ANTHROPIC_MODEL = None  # type: ignore[assignment]
MAX_PAPER_TEXT_CHARS = None  # type: ignore[assignment]
PARSER_BACKEND = None  # type: ignore[assignment]
PAPER_PATH = None  # type: ignore[assignment]


def apply_settings(settings: AppSettings) -> None:
    """Project structured settings onto module-level constants."""
    global WORKSPACE_ROOT, OUTPUTS_DIR, LOGS_DIR, PROMPTS_DIR
    global MAX_REVIEW_ITERATIONS, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
    global ANTHROPIC_API_KEY, ANTHROPIC_MODEL, MAX_PAPER_TEXT_CHARS, PARSER_BACKEND
    global PAPER_PATH

    WORKSPACE_ROOT = settings.workspace_root
    OUTPUTS_DIR = settings.outputs_dir
    LOGS_DIR = settings.logs_dir
    PROMPTS_DIR = settings.prompts_dir
    PAPER_PATH = settings.paper_path
    MAX_REVIEW_ITERATIONS = settings.workflow.max_review_iterations
    OPENAI_API_KEY = settings.llm.openai_api_key
    OPENAI_BASE_URL = settings.llm.openai_base_url
    OPENAI_MODEL = settings.llm.openai_model
    ANTHROPIC_API_KEY = settings.llm.anthropic_api_key
    ANTHROPIC_MODEL = settings.llm.anthropic_model
    MAX_PAPER_TEXT_CHARS = settings.parser.max_paper_text_chars
    PARSER_BACKEND = settings.parser.backend


apply_settings(LegacySettingsProvider().get_settings())
