"""Tests for LLM exception chain formatting and OpenAI error translation."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx
from openai import APIConnectionError

from configuration.models import LLMConfig
from providers.llm.errors import LLMProviderAPIError
from providers.llm.exception_chain import format_exception_chain, root_exception_label
from providers.llm.models import LLMMessage
from providers.llm.openai_errors import translate_openai_error
from providers.llm.openai_provider import OpenAIProvider


class ExceptionChainTest(unittest.TestCase):
    def test_format_exception_chain_includes_root_ssl_error(self) -> None:
        root = httpx.ConnectError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol")
        wrapped = APIConnectionError(request=MagicMock())
        wrapped.__cause__ = root
        text = format_exception_chain(wrapped)
        self.assertIn("APIConnectionError", text)
        self.assertIn("ConnectError", text)
        self.assertIn("UNEXPECTED_EOF_WHILE_READING", text)

    def test_root_exception_label(self) -> None:
        root = httpx.ConnectError("boom")
        wrapped = APIConnectionError(request=MagicMock())
        wrapped.__cause__ = root
        self.assertIn("ConnectError", root_exception_label(wrapped))

    def test_translate_openai_error_preserves_chain(self) -> None:
        root = httpx.ConnectError("tls failed")
        wrapped = APIConnectionError(request=MagicMock())
        wrapped.__cause__ = root
        translated = translate_openai_error(wrapped)
        self.assertIsInstance(translated, LLMProviderAPIError)
        self.assertIn("ConnectError", str(translated))
        self.assertIn("tls failed", str(translated))


class OpenAIProviderErrorTest(unittest.TestCase):
    @patch("providers.llm.openai_provider.OpenAI")
    def test_generate_raises_provider_error_with_chain(self, openai_cls: MagicMock) -> None:
        client = MagicMock()
        openai_cls.return_value = client
        root = httpx.ConnectError("tls failed")
        wrapped = APIConnectionError(request=MagicMock())
        wrapped.__cause__ = root
        client.chat.completions.create.side_effect = wrapped
        provider = OpenAIProvider(LLMConfig(openai_api_key="test-key"))
        with self.assertRaises(LLMProviderAPIError) as ctx:
            provider.generate([LLMMessage(role="user", content="hello")])
        self.assertIn("ConnectError", str(ctx.exception))
