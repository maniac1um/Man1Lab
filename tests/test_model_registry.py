"""Tests for the model registry."""

from __future__ import annotations

import ast
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from configuration.models import LLMConfig, ModelProfileSpec
from providers.llm.manager import LLMManager
from providers.llm.models import ModelProfile
from providers.llm.profiles import ensure_profiles, infer_legacy_provider
from providers.llm.provider_registry import create_default_registry
from providers.llm.registry import ModelRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolver(reference: str) -> str:
    return {
        "OPENAI_API_KEY": "test-key",
        "MISSING_KEY": "",
    }.get(reference, "")


def _openai_profile(name: str = "default", *, enabled: bool = True) -> ModelProfile:
    return ModelProfile(
        profile_name=name,
        provider="openai",
        model="gpt-4o-mini",
        api_key_reference="OPENAI_API_KEY",
        enabled=enabled,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _config_with_profiles(**overrides: object) -> LLMConfig:
    profiles = {
        "default": ModelProfileSpec(
            provider="openai",
            model="gpt-4o-mini",
            api_key_reference="OPENAI_API_KEY",
        ),
        "deepseek": ModelProfileSpec(
            provider="deepseek",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key_reference="OPENAI_API_KEY",
            enabled=False,
        ),
    }
    return LLMConfig(
        active="default",
        profiles=profiles,
        openai_api_key="test-key",
        **overrides,
    )


class LegacyCompatibilityTest(unittest.TestCase):
    def test_ensure_profiles_migrates_legacy_openai_configuration(self) -> None:
        config = LLMConfig(
            openai_api_key="legacy-key",
            openai_model="gpt-4o-mini",
            openai_base_url="",
        )
        migrated = ensure_profiles(config)
        self.assertEqual(migrated.active, "default")
        self.assertIn("default", migrated.profiles or {})
        self.assertEqual(migrated.profiles["default"].provider, "openai")

    def test_ensure_profiles_migrates_legacy_deepseek_configuration(self) -> None:
        config = LLMConfig(
            openai_api_key="legacy-key",
            openai_model="deepseek-chat",
            openai_base_url="https://api.deepseek.com",
        )
        migrated = ensure_profiles(config)
        self.assertEqual(migrated.profiles["default"].provider, "deepseek")

    def test_infer_legacy_provider_detects_deepseek(self) -> None:
        config = LLMConfig(openai_model="deepseek-chat", openai_base_url="https://api.deepseek.com")
        self.assertEqual(infer_legacy_provider(config), "deepseek")


class ModelRegistryTest(unittest.TestCase):
    def test_registry_loads_profiles_and_active_profile(self) -> None:
        registry = ModelRegistry(_config_with_profiles(), api_key_resolver=_resolver)
        self.assertEqual(registry.active_profile_name, "default")
        active = registry.get_active_profile()
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.model, "gpt-4o-mini")
        self.assertEqual(len(registry.list_profiles()), 2)

    def test_registry_switch_active_profile(self) -> None:
        registry = ModelRegistry(_config_with_profiles(), api_key_resolver=_resolver)
        registry.set_active_profile("deepseek")
        enabled_deepseek = ModelProfile(
            profile_name="deepseek",
            provider="deepseek",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key_reference="OPENAI_API_KEY",
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        registry.add_profile(enabled_deepseek)
        result = registry.set_active_profile("deepseek")
        self.assertTrue(result.valid)
        self.assertEqual(registry.active_profile_name, "deepseek")

    def test_registry_detects_duplicate_profile_names(self) -> None:
        registry = ModelRegistry(LLMConfig(active="a", profiles={}), api_key_resolver=_resolver)
        timestamp = datetime.now(UTC)
        registry._profiles["a"] = ModelProfile(
            profile_name="shared",
            provider="openai",
            model="gpt-4o-mini",
            api_key_reference="OPENAI_API_KEY",
            created_at=timestamp,
            updated_at=timestamp,
        )
        registry._profiles["b"] = ModelProfile(
            profile_name="shared",
            provider="openai",
            model="gpt-4o",
            api_key_reference="OPENAI_API_KEY",
            created_at=timestamp,
            updated_at=timestamp,
        )
        result = registry.validate()
        self.assertFalse(result.valid)
        self.assertTrue(any(item.code == "profile.duplicate" for item in result.errors))

    def test_registry_detects_unknown_provider(self) -> None:
        registry = ModelRegistry(LLMConfig(active="default", profiles={}), api_key_resolver=_resolver)
        registry.add_profile(
            ModelProfile(
                profile_name="default",
                provider="unknown",
                model="gpt-4o-mini",
                api_key_reference="OPENAI_API_KEY",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        result = registry.validate()
        self.assertFalse(result.valid)
        self.assertTrue(any(item.code == "profile.unknown_provider" for item in result.errors))

    def test_registry_detects_disabled_active_profile(self) -> None:
        config = LLMConfig(
            active="deepseek",
            profiles={
                "deepseek": ModelProfileSpec(
                    provider="deepseek",
                    model="deepseek-chat",
                    api_key_reference="OPENAI_API_KEY",
                    enabled=False,
                )
            },
        )
        registry = ModelRegistry(config, api_key_resolver=_resolver)
        result = registry.validate()
        self.assertFalse(result.valid)
        self.assertTrue(any(item.code == "active.disabled" for item in result.errors))

    def test_registry_detects_missing_api_reference(self) -> None:
        registry = ModelRegistry(LLMConfig(active="default", profiles={}), api_key_resolver=_resolver)
        registry.add_profile(
            ModelProfile(
                profile_name="default",
                provider="openai",
                model="gpt-4o-mini",
                api_key_reference="",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        result = registry.validate()
        self.assertFalse(result.valid)
        self.assertTrue(any(item.code == "profile.missing_api_reference" for item in result.errors))

    def test_registry_rename_and_remove_profile(self) -> None:
        registry = ModelRegistry(_config_with_profiles(), api_key_resolver=_resolver)
        registry.rename_profile("deepseek", "deepseek-prod")
        self.assertIsNone(registry.get_profile("deepseek"))
        self.assertIsNotNone(registry.get_profile("deepseek-prod"))
        registry.remove_profile("deepseek-prod")
        self.assertEqual(len(registry.list_profiles()), 1)

    def test_registry_validation_never_raises_on_load(self) -> None:
        config = LLMConfig(
            active="missing",
            profiles={
                "default": ModelProfileSpec(provider="", model="", api_key_reference=""),
            },
        )
        registry = ModelRegistry(config, api_key_resolver=_resolver)
        self.assertFalse(registry.last_validation.valid)


class ManagerIntegrationTest(unittest.TestCase):
    def test_manager_resolves_provider_from_active_profile(self) -> None:
        manager = LLMManager(_config_with_profiles(), provider_registry=create_default_registry())
        manager._model_registry = ModelRegistry(_config_with_profiles(), api_key_resolver=_resolver)
        manager._provider = manager._resolve_provider()
        self.assertTrue(manager.has_active_provider())
        self.assertEqual(manager.active_provider_name, "openai")

    def test_manager_without_valid_profile_has_no_provider(self) -> None:
        empty_resolver = lambda reference: ""
        manager = LLMManager(
            LLMConfig(),
            model_registry=ModelRegistry(LLMConfig(), api_key_resolver=empty_resolver),
        )
        self.assertFalse(manager.has_active_provider())

    @patch("providers.llm.openai_provider.OpenAI")
    def test_manager_delegates_through_active_profile(self, openai_cls: MagicMock) -> None:
        client = MagicMock()
        openai_cls.return_value = client
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="generated"))
        ]
        manager = LLMManager(_config_with_profiles(), provider_registry=create_default_registry())
        manager._model_registry = ModelRegistry(_config_with_profiles(), api_key_resolver=_resolver)
        manager._provider = manager._resolve_provider()
        from providers.llm.models import LLMMessage

        result = manager.generate([LLMMessage(role="user", content="hello")])
        self.assertEqual(result, "generated")


class ModelRegistryBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "agents",
        "discovery",
        "providers.github",
        "providers.embedded",
        "providers.noop",
        "openai",
        "anthropic",
        "httpx",
        "requests",
    )

    def test_model_registry_has_no_forbidden_imports(self) -> None:
        offenders: list[str] = []
        for path in (REPO_ROOT / "src" / "providers" / "llm" / "registry.py", REPO_ROOT / "src" / "providers" / "llm" / "profiles.py"):
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
                if root in self._FORBIDDEN_ROOTS or module.startswith("providers.llm.openai_provider"):
                    if path.name == "registry.py":
                        offenders.append(f"{path.name}: {module}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
