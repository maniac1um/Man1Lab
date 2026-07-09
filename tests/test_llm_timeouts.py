"""Tests for LLM HTTP timeout configuration."""

from __future__ import annotations

import unittest

import httpx

from configuration.models import LLMConfig
from providers.llm.timeouts import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    build_openai_client_timeout,
)


class LLMTimeoutConfigTest(unittest.TestCase):
    def test_default_connect_timeout_exceeds_openai_sdk_default(self) -> None:
        self.assertGreater(DEFAULT_CONNECT_TIMEOUT_SECONDS, 5.0)

    def test_build_openai_client_timeout_uses_config(self) -> None:
        config = LLMConfig(
            llm_connect_timeout_seconds=45.0,
            llm_read_timeout_seconds=300.0,
            llm_write_timeout_seconds=301.0,
            llm_pool_timeout_seconds=46.0,
        )
        timeout = build_openai_client_timeout(config)
        self.assertIsInstance(timeout, httpx.Timeout)
        self.assertEqual(timeout.connect, 45.0)
        self.assertEqual(timeout.read, 300.0)
        self.assertEqual(timeout.write, 301.0)
        self.assertEqual(timeout.pool, 46.0)
