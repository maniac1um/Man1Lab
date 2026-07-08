"""Tests for model management CLI commands."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from configuration.models import LLMConfig, ModelProfileSpec
from interfaces.cli.app import app
from providers.llm.model_management import (
    CurrentModelReport,
    ModelChangeReport,
    ModelListReport,
    ModelProfileSummary,
    ModelTestReport,
)
from providers.llm.models import RegistryDiagnostic, RegistryValidationResult

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]


def _list_report() -> ModelListReport:
    return ModelListReport(
        profiles=[
            ModelProfileSummary(
                profile_name="default",
                provider="openai",
                model="gpt-4o-mini",
                enabled=True,
                active=True,
                description="Default profile",
            ),
            ModelProfileSummary(
                profile_name="claude",
                provider="anthropic",
                model="claude-sonnet-4",
                enabled=False,
                active=False,
                description="Claude profile",
            ),
        ]
    )


class ModelCLITest(unittest.TestCase):
    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_list(self, get_platform: MagicMock) -> None:
        get_platform.return_value.list_models.return_value = _list_report()
        result = runner.invoke(app, ["model", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("* default", result.stdout)
        self.assertIn("claude", result.stdout)
        get_platform.return_value.list_models.assert_called_once()

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_current(self, get_platform: MagicMock) -> None:
        get_platform.return_value.current_model.return_value = CurrentModelReport(
            profile_name="default",
            provider="openai",
            model="gpt-4o-mini",
            base_url="",
            api_key_reference="OPENAI_API_KEY",
            enabled=True,
        )
        result = runner.invoke(app, ["model", "current"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Active Profile: default", result.stdout)

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_use(self, get_platform: MagicMock) -> None:
        get_platform.return_value.use_model.return_value = ModelChangeReport(
            successful=True,
            message="Active profile changed",
            active_profile="claude",
        )
        result = runner.invoke(app, ["model", "use", "claude"])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.use_model.assert_called_once_with("claude")
        self.assertIn("Active profile changed", result.stdout)

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_add_interactive(self, get_platform: MagicMock) -> None:
        get_platform.return_value.add_model.return_value = ModelChangeReport(
            successful=True,
            message="Profile 'local' added.",
            active_profile="default",
        )
        result = runner.invoke(
            app,
            ["model", "add"],
            input="local\nopenai\ngpt-4o-mini\n\nOPENAI_API_KEY\n\n\n\n",
        )
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.add_model.assert_called_once()

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_remove_blocks_active_without_force(self, get_platform: MagicMock) -> None:
        get_platform.return_value.remove_model.return_value = ModelChangeReport(
            successful=False,
            message="Cannot remove active profile 'default' without --force.",
        )
        result = runner.invoke(app, ["model", "remove", "default"])
        self.assertNotEqual(result.exit_code, 0)
        get_platform.return_value.remove_model.assert_called_once_with("default", force=False)

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_remove_force(self, get_platform: MagicMock) -> None:
        get_platform.return_value.remove_model.return_value = ModelChangeReport(
            successful=True,
            message="Profile 'default' removed.",
            active_profile="claude",
        )
        result = runner.invoke(app, ["model", "remove", "default", "--force"])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.remove_model.assert_called_once_with("default", force=True)

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_rename(self, get_platform: MagicMock) -> None:
        get_platform.return_value.rename_model.return_value = ModelChangeReport(
            successful=True,
            message="Profile renamed to 'claude-prod'.",
            active_profile="claude-prod",
        )
        result = runner.invoke(app, ["model", "rename", "claude", "claude-prod"])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.rename_model.assert_called_once_with("claude", "claude-prod")

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_test(self, get_platform: MagicMock) -> None:
        get_platform.return_value.test_model.return_value = ModelTestReport(
            profile_name="default",
            provider="openai",
            model="gpt-4o-mini",
            authentication="ok",
            connection="ok",
            latency_ms=12.5,
            result="passed",
            message="OpenAI client configured.",
        )
        result = runner.invoke(app, ["model", "test"])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.test_model.assert_called_once_with(None)
        self.assertIn("Result: passed", result.stdout)

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_validate_success(self, get_platform: MagicMock) -> None:
        get_platform.return_value.validate_models.return_value = RegistryValidationResult(valid=True)
        result = runner.invoke(app, ["model", "validate"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Validation passed.", result.stdout)

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_validate_failure_exit_code(self, get_platform: MagicMock) -> None:
        get_platform.return_value.validate_models.return_value = RegistryValidationResult(
            valid=False,
            diagnostics=(
                RegistryDiagnostic(
                    level="error",
                    code="active.missing_api_key",
                    message="Missing API key.",
                    profile_name="default",
                ),
            ),
        )
        result = runner.invoke(app, ["model", "validate"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Validation failed.", result.stdout + result.stderr)


class FacadeModelDelegationTest(unittest.TestCase):
    def test_facade_delegates_model_operations(self) -> None:
        from application import Man1Lab as Platform

        manager = MagicMock()
        manager.list_models.return_value = _list_report()
        with patch("application.facade.LLMManager", return_value=manager):
            platform = Platform(initialize_configuration=False, configure_logging=False)
            platform.list_models()
            platform.use_model("claude")
            platform.validate_models()
        manager.list_models.assert_called_once()
        manager.use_model.assert_called_once_with("claude")
        manager.validate_models.assert_called_once()


class ModelPersistenceTest(unittest.TestCase):
    def test_registry_persistence_round_trip(self) -> None:
        from providers.llm.manager import LLMManager
        from providers.llm.persistence import load_persisted_llm_config, merge_llm_config

        config = LLMConfig(
            active="default",
            profiles={
                "default": ModelProfileSpec(
                    provider="openai",
                    model="gpt-4o-mini",
                    api_key_reference="OPENAI_API_KEY",
                )
            },
            openai_api_key="test-key",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "user_profiles.yaml"
            manager = LLMManager(config, persistence_path=path)
            manager.use_model("default")
            loaded = load_persisted_llm_config(path)
            assert loaded is not None
            merged = merge_llm_config(config, loaded)
            self.assertEqual(merged.active, "default")
            self.assertIn("default", merged.profiles or {})


class ModelCLIBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "agents",
        "providers.llm",
        "openai",
        "anthropic",
    )

    def test_model_cli_has_no_forbidden_imports(self) -> None:
        path = REPO_ROOT / "interfaces" / "cli" / "commands" / "model.py"
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
            if root in self._FORBIDDEN_ROOTS or module.startswith("providers."):
                offenders.append(f"{path.name}: {module}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
