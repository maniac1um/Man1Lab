"""Tests for the Anthropic LLM provider."""

from __future__ import annotations

import ast
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from anthropic import AuthenticationError, RateLimitError

from configuration.models import LLMConfig, ModelProfileSpec
from providers.llm.anthropic_provider import AnthropicProvider
from providers.llm.errors import LLMProviderAuthenticationError, LLMProviderRateLimitError
from providers.llm.manager import LLMManager
from providers.llm.models import LLMMessage, ModelProfile
from providers.llm.provider_registry import create_default_registry
from providers.llm.registry import ModelRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]


def _anthropic_resolver(reference: str) -> str:
    return {
        "ANTHROPIC_API_KEY": "anthropic-test-key",
        "OPENAI_API_KEY": "",
    }.get(reference, "")


def _claude_config() -> LLMConfig:
    return LLMConfig(
        active="claude",
        profiles={
            "claude": ModelProfileSpec(
                provider="anthropic",
                model="claude-sonnet-4",
                api_key_reference="ANTHROPIC_API_KEY",
                enabled=True,
            )
        },
        anthropic_api_key="anthropic-test-key",
        anthropic_model="claude-sonnet-4",
    )


class AnthropicProviderRegistrationTest(unittest.TestCase):
    def test_default_registry_includes_anthropic(self) -> None:
        self.assertIn("anthropic", create_default_registry().list_providers())

    def test_registry_resolves_anthropic_provider(self) -> None:
        registry = create_default_registry()
        provider = registry.resolve("anthropic", _claude_config())
        self.assertEqual(provider.provider_name, "anthropic")


class AnthropicProviderBehaviorTest(unittest.TestCase):
    @patch("providers.llm.anthropic_provider.Anthropic")
    def test_generate_delegates_to_messages_api(self, anthropic_cls: MagicMock) -> None:
        client = MagicMock()
        anthropic_cls.return_value = client
        block = MagicMock(type="text", text="hello claude")
        client.messages.create.return_value.content = [block]

        provider = AnthropicProvider(_claude_config())
        result = provider.generate(
            [
                LLMMessage(role="system", content="system prompt"),
                LLMMessage(role="user", content="hello"),
            ]
        )

        self.assertEqual(result, "hello claude")
        client.messages.create.assert_called_once()
        kwargs = client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["system"], "system prompt")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "hello"}])

    @patch("providers.llm.anthropic_provider.Anthropic")
    def test_stream_delegates_to_text_stream(self, anthropic_cls: MagicMock) -> None:
        client = MagicMock()
        anthropic_cls.return_value = client
        stream_ctx = MagicMock()
        stream_ctx.__enter__.return_value.text_stream = iter(["chunk-1", "chunk-2"])
        client.messages.stream.return_value = stream_ctx

        provider = AnthropicProvider(_claude_config())
        chunks = list(provider.stream([LLMMessage(role="user", content="hello")]))

        self.assertEqual(chunks, ["chunk-1", "chunk-2"])
        client.messages.stream.assert_called_once()

    @patch("providers.llm.anthropic_provider.Anthropic")
    def test_health_check_returns_ok_on_success(self, anthropic_cls: MagicMock) -> None:
        client = MagicMock()
        anthropic_cls.return_value = client
        provider = AnthropicProvider(_claude_config())
        health = provider.health_check()
        self.assertEqual(health.status, "ok")
        self.assertEqual(health.provider, "anthropic")
        client.messages.create.assert_called_once()

    @patch("providers.llm.anthropic_provider.Anthropic")
    def test_health_check_never_raises(self, anthropic_cls: MagicMock) -> None:
        client = MagicMock()
        anthropic_cls.return_value = client
        client.messages.create.side_effect = AuthenticationError(
            "invalid key",
            response=MagicMock(status_code=401),
            body=None,
        )
        provider = AnthropicProvider(_claude_config())
        health = provider.health_check()
        self.assertEqual(health.status, "error")
        self.assertIn("invalid key", health.message)

    @patch("providers.llm.anthropic_provider.Anthropic")
    def test_generate_translates_authentication_error(self, anthropic_cls: MagicMock) -> None:
        client = MagicMock()
        anthropic_cls.return_value = client
        client.messages.create.side_effect = AuthenticationError(
            "invalid key",
            response=MagicMock(status_code=401),
            body=None,
        )
        provider = AnthropicProvider(_claude_config())
        with self.assertRaises(LLMProviderAuthenticationError):
            provider.generate([LLMMessage(role="user", content="hello")])

    @patch("providers.llm.anthropic_provider.Anthropic")
    def test_generate_translates_rate_limit_error(self, anthropic_cls: MagicMock) -> None:
        client = MagicMock()
        anthropic_cls.return_value = client
        client.messages.create.side_effect = RateLimitError(
            "rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        provider = AnthropicProvider(_claude_config())
        with self.assertRaises(LLMProviderRateLimitError):
            provider.generate([LLMMessage(role="user", content="hello")])

    @patch("providers.llm.anthropic_provider.Anthropic")
    def test_supported_models_and_metadata(self, anthropic_cls: MagicMock) -> None:
        anthropic_cls.return_value = MagicMock()
        provider = AnthropicProvider(_claude_config())
        self.assertEqual(provider.provider_name, "anthropic")
        self.assertIn("claude-sonnet-4", provider.supported_models())


class AnthropicManagerIntegrationTest(unittest.TestCase):
    @patch("providers.llm.anthropic_provider.Anthropic")
    def test_manager_resolves_anthropic_active_profile(self, anthropic_cls: MagicMock) -> None:
        client = MagicMock()
        anthropic_cls.return_value = client
        block = MagicMock(type="text", text="via manager")
        client.messages.create.return_value.content = [block]

        config = _claude_config()
        manager = LLMManager(
            config,
            model_registry=ModelRegistry(config, api_key_resolver=_anthropic_resolver),
            provider_registry=create_default_registry(),
        )

        self.assertTrue(manager.has_active_provider())
        self.assertEqual(manager.active_provider_name, "anthropic")
        self.assertEqual(manager.active_profile_name, "claude")
        result = manager.generate([LLMMessage(role="user", content="hello")])
        self.assertEqual(result, "via manager")

    def test_model_registry_builds_anthropic_provider_config(self) -> None:
        config = _claude_config()
        registry = ModelRegistry(config, api_key_resolver=_anthropic_resolver)
        profile = registry.get_profile("claude")
        assert profile is not None
        provider_config = registry.build_provider_config(profile, "anthropic-test-key")
        self.assertEqual(provider_config.anthropic_api_key, "anthropic-test-key")
        self.assertEqual(provider_config.anthropic_model, "claude-sonnet-4")


class AnthropicProviderBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "agents",
        "discovery",
        "providers.github",
    )

    def test_anthropic_provider_has_no_forbidden_imports(self) -> None:
        path = REPO_ROOT / "src" / "providers" / "llm" / "anthropic_provider.py"
        offenders: list[str] = []
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            if module is None:
                continue
            root = module.split(".", 1)[0]
            if root in self._FORBIDDEN_ROOTS:
                offenders.append(f"{path.name}: {module}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
