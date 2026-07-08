"""Tests for the LLM provider foundation."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from configuration.models import LLMConfig
from llm.compat import LLMManagerCompleteAdapter
from llm.factory import build_llm_provider, build_planner_llm_provider
from llm.provider import LLMMessage
from providers.llm.deepseek_provider import DEEPSEEK_BASE_URL, DeepSeekProvider
from providers.llm.manager import LLMManager
from providers.llm.openai_provider import OpenAIProvider
from providers.llm.provider_registry import ProviderRegistry, create_default_registry
from providers.llm.registry import ModelRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]


class ProviderRegistryTest(unittest.TestCase):
    def test_default_registry_lists_openai_and_deepseek(self) -> None:
        registry = create_default_registry()
        self.assertEqual(registry.list_providers(), ["anthropic", "deepseek", "openai"])

    def test_registry_resolves_provider(self) -> None:
        registry = create_default_registry()
        config = LLMConfig(openai_api_key="test-key", openai_model="gpt-4o-mini")
        provider = registry.resolve("openai", config)
        self.assertEqual(provider.provider_name, "openai")

    def test_registry_unknown_provider_raises(self) -> None:
        registry = ProviderRegistry()
        with self.assertRaises(KeyError):
            registry.resolve("missing", LLMConfig())


class LLMManagerTest(unittest.TestCase):
    def test_manager_selects_openai_by_default(self) -> None:
        manager = LLMManager(LLMConfig(openai_api_key="test-key", openai_model="gpt-4o-mini"))
        self.assertEqual(manager.active_provider_name, "openai")
        self.assertTrue(manager.has_active_provider())

    def test_manager_selects_deepseek_from_base_url(self) -> None:
        manager = LLMManager(
            LLMConfig(
                openai_api_key="test-key",
                openai_base_url="https://api.deepseek.com",
                openai_model="deepseek-chat",
            )
        )
        self.assertEqual(manager.active_provider_name, "deepseek")
        self.assertEqual(manager.get_provider().provider_name, "deepseek")

    def test_manager_without_credentials_has_no_active_provider(self) -> None:
        empty_resolver = lambda reference: ""
        manager = LLMManager(
            LLMConfig(),
            model_registry=ModelRegistry(LLMConfig(), api_key_resolver=empty_resolver),
        )
        self.assertFalse(manager.has_active_provider())
        self.assertIsNone(manager.active_provider_name)

    def test_manager_delegates_generate(self) -> None:
        manager = LLMManager(LLMConfig(openai_api_key="test-key"))
        provider = MagicMock()
        provider.generate.return_value = "ok"
        manager._provider = provider
        messages = [LLMMessage(role="user", content="hello")]
        self.assertEqual(manager.generate(messages), "ok")
        provider.generate.assert_called_once()

    def test_manager_delegates_health_check(self) -> None:
        manager = LLMManager(LLMConfig(openai_api_key="test-key"))
        provider = MagicMock()
        provider.health_check.return_value.status = "ok"
        manager._provider = provider
        manager.health_check()
        provider.health_check.assert_called_once()


class OpenAIProviderTest(unittest.TestCase):
    @patch("providers.llm.openai_provider.OpenAI")
    def test_generate_uses_chat_completions(self, openai_cls: MagicMock) -> None:
        client = MagicMock()
        openai_cls.return_value = client
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="generated"))
        ]
        config = LLMConfig(openai_api_key="test-key", openai_model="gpt-4o-mini")
        provider = OpenAIProvider(config)
        result = provider.generate([LLMMessage(role="user", content="hello")])
        self.assertEqual(result, "generated")
        client.chat.completions.create.assert_called_once()

    @patch("providers.llm.openai_provider.OpenAI")
    def test_supported_models_and_health_check(self, openai_cls: MagicMock) -> None:
        openai_cls.return_value = MagicMock()
        provider = OpenAIProvider(LLMConfig(openai_api_key="test-key", openai_model="gpt-4o-mini"))
        self.assertIn("gpt-4o-mini", provider.supported_models())
        health = provider.health_check()
        self.assertEqual(health.provider, "openai")
        self.assertEqual(health.status, "ok")


class DeepSeekProviderTest(unittest.TestCase):
    @patch("providers.llm.openai_provider.OpenAI")
    def test_deepseek_defaults_to_openai_compatible_endpoint(self, openai_cls: MagicMock) -> None:
        openai_cls.return_value = MagicMock()
        provider = DeepSeekProvider(
            LLMConfig(openai_api_key="test-key", openai_model="deepseek-chat")
        )
        self.assertEqual(provider.provider_name, "deepseek")
        self.assertIn("deepseek-chat", provider.supported_models())
        _, kwargs = openai_cls.call_args
        self.assertEqual(kwargs["base_url"], DEEPSEEK_BASE_URL)


class FactoryAndFacadeAdapterTest(unittest.TestCase):
    @patch("llm.factory.LLMManager")
    def test_build_llm_provider_uses_manager_when_configured(self, manager_cls: MagicMock) -> None:
        manager = manager_cls.return_value
        manager.has_active_provider.return_value = True
        provider = build_llm_provider()
        self.assertIsInstance(provider, LLMManagerCompleteAdapter)

    @patch("llm.factory.LLMManager")
    def test_build_planner_llm_provider_falls_back_to_mock(self, manager_cls: MagicMock) -> None:
        manager = manager_cls.return_value
        manager.has_active_provider.return_value = False
        provider = build_planner_llm_provider()
        self.assertEqual(provider.__class__.__name__, "MockLLMProvider")


class LLMProviderBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "agents",
        "discovery",
        "providers.github",
        "providers.embedded",
        "providers.noop",
    )

    def test_llm_provider_package_has_no_forbidden_imports(self) -> None:
        llm_root = REPO_ROOT / "providers" / "llm"
        offenders: list[str] = []
        for path in llm_root.rglob("*.py"):
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
                if any(module == root or module.startswith(f"{root}.") for root in self._FORBIDDEN_ROOTS):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {module}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
