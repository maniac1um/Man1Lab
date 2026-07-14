"""Provider-level errors shared across LLM adapters."""

from __future__ import annotations


class LLMProviderError(RuntimeError):
    """Translated provider error safe to surface above the adapter boundary."""


class LLMProviderAuthenticationError(LLMProviderError):
    """Authentication failed for the configured provider."""


class LLMProviderRateLimitError(LLMProviderError):
    """Provider rate limit exceeded."""


class LLMProviderAPIError(LLMProviderError):
    """Generic provider API failure."""
