"""Tests for first-run init wizard, model import/export, and doctor LLM checks."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from application.facade import ModelSetupReport
from application.lifecycle import DoctorCheck, DoctorReport
from application.lifecycle.init_wizard import (
    InitWizardRequest,
    resolve_provider_choice,
    resolve_wizard_profile,
    write_api_key_to_env,
)
from application.lifecycle.llm_doctor import run_llm_doctor_checks
from configuration.models import LLMConfig, ModelProfileSpec
from interfaces.cli.app import app
from providers.llm.manager import LLMManager
from providers.llm.model_management import ModelTestReport
from providers.llm.persistence import (
    ModelImportReport,
    export_portable_config,
    import_portable_config,
    load_persisted_llm_config,
)
from providers.llm.registry import ModelRegistry

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]


def _openai_config(api_key: str = "test-key") -> LLMConfig:
    return LLMConfig(
        active="default",
        profiles={
            "default": ModelProfileSpec(
                provider="openai",
                model="gpt-4o-mini",
                api_key_reference="OPENAI_API_KEY",
            )
        },
        openai_api_key=api_key,
    )


def _registry(config: LLMConfig | None = None) -> ModelRegistry:
    cfg = config or _openai_config()
    return ModelRegistry(cfg, api_key_resolver=lambda _ref: cfg.openai_api_key or "")


class InitWizardCLITest(unittest.TestCase):
    @patch("interfaces.cli.commands.init.get_platform")
    def test_init_skip_model_config(self, get_platform: MagicMock) -> None:
        from application.lifecycle import InitAction, InitReport

        get_platform.return_value.init.return_value = InitReport(
            successful=True,
            actions=[InitAction(path=Path("."), action="ready", message="ok")],
            next_steps=["Run doctor"],
        )
        result = runner.invoke(app, ["init", "--skip-model-config"])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.init.assert_called_once()
        get_platform.return_value.setup_first_model.assert_not_called()
        self.assertIn("Next steps", result.stdout)

    @patch("interfaces.cli.commands.init.getpass.getpass", return_value="sk-test")
    @patch("interfaces.cli.commands.init.get_platform")
    def test_init_openai_wizard_flow(self, get_platform: MagicMock, _getpass: MagicMock) -> None:
        from application.lifecycle import InitAction, InitReport

        get_platform.return_value.init.return_value = InitReport(
            successful=True,
            actions=[InitAction(path=Path("."), action="ready", message="ok")],
            next_steps=[],
        )
        get_platform.return_value.setup_first_model.return_value = ModelSetupReport(
            successful=True,
            message="First model profile configured.",
            profile_name="default",
            provider="openai",
            model="gpt-4o-mini",
        )
        result = runner.invoke(
            app,
            ["init"],
            input="y\n\n1\n\n\n\n\n\n",
        )
        self.assertEqual(result.exit_code, 0, msg=result.stdout + result.stderr)
        get_platform.return_value.setup_first_model.assert_called_once()
        request = get_platform.return_value.setup_first_model.call_args.args[0]
        self.assertEqual(request.provider, "openai")
        self.assertEqual(request.api_key, "sk-test")
        self.assertIn("Active model: default", result.stdout)

    @patch("interfaces.cli.commands.init.getpass.getpass", return_value="ds-key")
    @patch("interfaces.cli.commands.init.get_platform")
    def test_init_deepseek_wizard_flow(self, get_platform: MagicMock, _getpass: MagicMock) -> None:
        from application.lifecycle import InitAction, InitReport

        get_platform.return_value.init.return_value = InitReport(
            successful=True,
            actions=[],
            next_steps=[],
        )
        get_platform.return_value.setup_first_model.return_value = ModelSetupReport(
            successful=True,
            message="ok",
            profile_name="deepseek",
            provider="deepseek",
            model="deepseek-chat",
        )
        result = runner.invoke(
            app,
            ["init"],
            input="y\ndeepseek\n2\n\n\n\n\n\n\n",
        )
        self.assertEqual(result.exit_code, 0, msg=result.stdout + result.stderr)
        request = get_platform.return_value.setup_first_model.call_args.args[0]
        self.assertEqual(request.provider, "deepseek")
        self.assertEqual(request.profile_name, "deepseek")

    @patch("interfaces.cli.commands.init.getpass.getpass", return_value="ant-key")
    @patch("interfaces.cli.commands.init.get_platform")
    def test_init_anthropic_wizard_flow(self, get_platform: MagicMock, _getpass: MagicMock) -> None:
        from application.lifecycle import InitAction, InitReport

        get_platform.return_value.init.return_value = InitReport(
            successful=True,
            actions=[],
            next_steps=[],
        )
        get_platform.return_value.setup_first_model.return_value = ModelSetupReport(
            successful=True,
            message="ok",
            profile_name="claude",
            provider="anthropic",
            model="claude-sonnet-4",
        )
        result = runner.invoke(
            app,
            ["init"],
            input="y\nclaude\n3\n\n\n\n\n\n\n",
        )
        self.assertEqual(result.exit_code, 0, msg=result.stdout + result.stderr)
        request = get_platform.return_value.setup_first_model.call_args.args[0]
        self.assertEqual(request.provider, "anthropic")
        self.assertEqual(request.profile_name, "claude")

    @patch("interfaces.cli.commands.init.get_platform")
    def test_init_decline_model_config(self, get_platform: MagicMock) -> None:
        from application.lifecycle import InitReport

        get_platform.return_value.init.return_value = InitReport(
            successful=True,
            actions=[],
            next_steps=["Run doctor"],
        )
        result = runner.invoke(app, ["init"], input="n\n")
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.setup_first_model.assert_not_called()
        self.assertIn("Next steps", result.stdout)


class InitWizardLifecycleTest(unittest.TestCase):
    def test_resolve_provider_choice(self) -> None:
        self.assertEqual(resolve_provider_choice("1"), "openai")
        self.assertEqual(resolve_provider_choice("anthropic"), "anthropic")

    def test_write_api_key_to_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            write_api_key_to_env(env_path, "OPENAI_API_KEY", "secret")
            self.assertIn("OPENAI_API_KEY=secret", env_path.read_text(encoding="utf-8"))

    def test_setup_first_model_delegates_through_facade(self) -> None:
        from application import Man1Lab as Platform

        manager = MagicMock()
        manager.add_model.return_value = MagicMock(successful=True, message="added")
        manager.use_model.return_value = MagicMock(successful=True, message="active")
        request = InitWizardRequest(
            profile_name="default",
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-test",
        )
        with patch("application.facade.LLMManager", return_value=manager):
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                platform = Platform(initialize_configuration=False, configure_logging=False)
                report = platform.setup_first_model(request, workspace_root=root)
        self.assertTrue(report.successful)
        manager.add_model.assert_called_once()
        manager.use_model.assert_called_once_with("default")


class ModelImportExportTest(unittest.TestCase):
    def test_export_excludes_secrets(self) -> None:
        config = _openai_config()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "profiles.yaml"
            manager = LLMManager(config, persistence_path=Path(temp_dir) / "user.yaml")
            export_path = manager.export_models(path)
            content = export_path.read_text(encoding="utf-8")
            self.assertIn("profiles:", content)
            self.assertIn("active:", content)
            self.assertNotIn("test-key", content)
            self.assertIn("api_key_reference", content)

    def test_import_duplicate_detection(self) -> None:
        config = _openai_config()
        registry = _registry(config)
        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = Path(temp_dir) / "portable.yaml"
            export_portable_config(
                registry.export_profiles(),
                active="default",
                base_config=config,
                path=export_path,
            )
            report = import_portable_config(registry, export_path)
            self.assertFalse(report.successful)
            self.assertIn("Duplicate", report.message)

    def test_import_replace(self) -> None:
        config = _openai_config()
        registry = _registry(config)
        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = Path(temp_dir) / "portable.yaml"
            export_portable_config(
                registry.export_profiles(),
                active="default",
                base_config=config,
                path=export_path,
            )
            report = import_portable_config(registry, export_path, replace=True)
            self.assertTrue(report.successful)
            self.assertIn("default", report.replaced)

    def test_import_skip_existing(self) -> None:
        config = _openai_config()
        registry = _registry(config)
        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = Path(temp_dir) / "portable.yaml"
            export_portable_config(
                registry.export_profiles(),
                active="default",
                base_config=config,
                path=export_path,
            )
            report = import_portable_config(registry, export_path, skip_existing=True)
            self.assertTrue(report.successful)
            self.assertIn("default", report.skipped)

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_export_cli(self, get_platform: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out = Path(temp_dir) / "export.yaml"
            get_platform.return_value.export_models.return_value = out
            result = runner.invoke(app, ["model", "export", str(out)])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.export_models.assert_called_once()

    @patch("interfaces.cli.commands.model.get_platform")
    def test_model_import_cli(self, get_platform: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "import.yaml"
            source.write_text("active: default\nprofiles: {}\n", encoding="utf-8")
            get_platform.return_value.import_models.return_value = ModelImportReport(
                successful=True,
                message="Imported 0 profile(s).",
                added=("new",),
            )
            result = runner.invoke(app, ["model", "import", str(source)])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.import_models.assert_called_once()


class DoctorLLMTest(unittest.TestCase):
    def test_doctor_llm_output(self) -> None:
        manager = MagicMock()
        profile = MagicMock()
        profile.profile_name = "claude"
        profile.provider = "anthropic"
        profile.model = "claude-sonnet-4"
        profile.api_key_reference = "ANTHROPIC_API_KEY"
        manager.model_registry.list_profiles.return_value = [profile]
        manager.model_registry.get_active_profile.return_value = profile
        manager.model_registry.resolve_api_key.return_value = "secret"
        manager.model_registry.validate.return_value = MagicMock(valid=True, errors=[])
        manager.has_active_provider.return_value = True
        manager.test_model.return_value = ModelTestReport(
            profile_name="claude",
            provider="anthropic",
            model="claude-sonnet-4",
            authentication="ok",
            connection="ok",
            latency_ms=10.0,
            result="passed",
            message="Healthy",
        )
        checks = run_llm_doctor_checks(manager)
        names = [check.name for check in checks]
        self.assertIn("LLM Profiles", names)
        self.assertIn("LLM Connection", names)

    @patch("interfaces.cli.commands.doctor.get_platform")
    def test_doctor_cli_llm_section(self, get_platform: MagicMock) -> None:
        get_platform.return_value.doctor.return_value = DoctorReport(
            healthy=True,
            checks=[
                DoctorCheck(name="Python", status="ok", message="3.12"),
                DoctorCheck(name="LLM Profiles", status="ok", message="2"),
                DoctorCheck(name="LLM Active", status="ok", message="claude"),
                DoctorCheck(name="LLM Connection", status="ok", message="Healthy"),
            ],
        )
        result = runner.invoke(app, ["doctor"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("LLM", result.stdout)
        self.assertIn("Active", result.stdout)


class InitWizardBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "agents",
        "providers",
        "openai",
        "anthropic",
        "coder",
        "runner",
    )

    def test_init_cli_has_no_forbidden_imports(self) -> None:
        path = REPO_ROOT / "interfaces" / "cli" / "commands" / "init.py"
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

    def test_facade_exports_setup_and_import_export(self) -> None:
        from application import Man1Lab as Platform

        manager = MagicMock()
        with patch("application.facade.LLMManager", return_value=manager):
            platform = Platform(initialize_configuration=False, configure_logging=False)
            with tempfile.TemporaryDirectory() as temp_dir:
                export_path = Path(temp_dir) / "out.yaml"
                manager.export_models.return_value = export_path
                platform.export_models(export_path)
                platform.import_models(export_path, replace=True)
        manager.export_models.assert_called_once()
        manager.import_models.assert_called_once_with(export_path, replace=True, skip_existing=False)


if __name__ == "__main__":
    unittest.main()
