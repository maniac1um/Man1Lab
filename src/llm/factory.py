"""Legacy LLM provider builders — require a runtime-owned LLMManager."""

from __future__ import annotations

import logging

from llm.compat import LLMManagerCompleteAdapter
from llm.mock_provider import MOCK_PLANNER_JSON, MockLLMProvider
from llm.provider import LLMProvider
from providers.llm.manager import LLMManager


def build_llm_provider(*, manager: LLMManager) -> LLMProvider:
    """Build an LLM port from a runtime-owned LLM manager."""
    if manager.has_active_provider():
        return LLMManagerCompleteAdapter(manager)
    logging.warning("OPENAI_API_KEY not set; using MockLLMProvider")
    return MockLLMProvider()


def build_planner_llm_provider(*, manager: LLMManager) -> LLMProvider:
    """Build a planner LLM port from a runtime-owned LLM manager."""
    if manager.has_active_provider():
        return LLMManagerCompleteAdapter(manager)
    return MockLLMProvider(MOCK_PLANNER_JSON)
