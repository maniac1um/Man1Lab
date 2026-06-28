import logging

import config
from llm.mock_provider import MOCK_PLANNER_JSON, MockLLMProvider
from llm.openai_provider import OpenAIProvider
from llm.provider import LLMProvider


def build_llm_provider() -> LLMProvider:
    if config.OPENAI_API_KEY:
        return OpenAIProvider()
    logging.warning("OPENAI_API_KEY not set; using MockLLMProvider")
    return MockLLMProvider()


def build_planner_llm_provider() -> LLMProvider:
    if config.OPENAI_API_KEY:
        return OpenAIProvider()
    return MockLLMProvider(MOCK_PLANNER_JSON)
