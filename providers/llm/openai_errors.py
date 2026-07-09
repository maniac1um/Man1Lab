"""Translate OpenAI SDK failures without swallowing root causes."""

from __future__ import annotations

from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, RateLimitError

from providers.llm.errors import (
    LLMProviderAPIError,
    LLMProviderAuthenticationError,
    LLMProviderError,
    LLMProviderRateLimitError,
)
from providers.llm.exception_chain import format_exception_chain


def translate_openai_error(exc: Exception) -> LLMProviderError:
    """Map SDK exceptions to provider errors while preserving the exception chain."""
    if isinstance(exc, AuthenticationError):
        return LLMProviderAuthenticationError(format_exception_chain(exc))
    if isinstance(exc, RateLimitError):
        return LLMProviderRateLimitError(format_exception_chain(exc))
    if isinstance(exc, (APIConnectionError, APITimeoutError, APIError)):
        return LLMProviderAPIError(format_exception_chain(exc))
    return LLMProviderAPIError(format_exception_chain(exc))
