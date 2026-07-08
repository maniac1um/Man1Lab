import logging

from configuration.models import LLMConfig
from llm.compat import LLMManagerCompleteAdapter
from llm.mock_provider import MOCK_PLANNER_JSON, MockLLMProvider
from llm.provider import LLMProvider
from providers.llm.manager import LLMManager


def _legacy_llm_config() -> LLMConfig:
    import config

    return LLMConfig(
        openai_api_key=config.OPENAI_API_KEY or "",
        openai_base_url=config.OPENAI_BASE_URL or "",
        openai_model=config.OPENAI_MODEL or "gpt-4o-mini",
        anthropic_api_key=config.ANTHROPIC_API_KEY or "",
        anthropic_model=config.ANTHROPIC_MODEL or "claude-3-5-haiku-latest",
    )


def build_llm_provider() -> LLMProvider:
    manager = LLMManager(_legacy_llm_config())
    if manager.has_active_provider():
        return LLMManagerCompleteAdapter(manager)
    logging.warning("OPENAI_API_KEY not set; using MockLLMProvider")
    return MockLLMProvider()


def build_planner_llm_provider() -> LLMProvider:
    manager = LLMManager(_legacy_llm_config())
    if manager.has_active_provider():
        return LLMManagerCompleteAdapter(manager)
    return MockLLMProvider(MOCK_PLANNER_JSON)
