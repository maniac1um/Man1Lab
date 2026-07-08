"""Tests for lifecycle workspace cleanup."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from application.lifecycle import CleanPolicy, CleanupReport, clean_workspace
from application.lifecycle.common import is_never_delete
from configuration.models import (
    AppSettings,
    DiscoveryConfig,
    ExecutionPlanningConfig,
    LLMConfig,
    LoggingConfig,
    ParserConfig,
    TrackingConfig,
    WorkflowConfig,
)
from interfaces.cli.app import app

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]


def _test_settings(temp_dir: Path) -> AppSettings:
    return AppSettings(
        workspace_root=temp_dir / "workspace" / "tasks",
        outputs_dir=temp_dir / "outputs",
        logs_dir=temp_dir / "logs",
        prompts_dir=Path("prompts"),
        paper_path=temp_dir / "paper.pdf",
        parser=ParserConfig(backend="pymupdf"),
        discovery=DiscoveryConfig(enabled=True),
        execution_planning=ExecutionPlanningConfig(enabled=True),
        workflow=WorkflowConfig(max_review_iterations=1),
        llm=LLMConfig(),
        logging=LoggingConfig(),
        tracking=TrackingConfig(enabled=False, backend="noop"),
    )


def _seed_safe_artifacts(root: Path) -> None:
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "outputs" / "run.txt").write_text("output", encoding="utf-8")
    (root / "logs" / "workflow.log").write_text("log", encoding="utf-8")
    (root / "mlruns" / "0").mkdir(parents=True)
    (root / ".pytest_cache" / "v").mkdir(parents=True)
    (root / "workspace" / "cache" / "entry").mkdir(parents=True)
    (root / "workspace" / "tmp" / "scratch").mkdir(parents=True)
    (root / "application" / "__pycache__").mkdir(parents=True)
    (root / "application" / "__pycache__" / "module.cpython-312.pyc").write_bytes(b"cache")


def _seed_protected_artifacts(root: Path) -> None:
    (root / "workspace" / "tasks" / "task-1").mkdir(parents=True, exist_ok=True)
    (root / "workspace" / "papers").mkdir(parents=True, exist_ok=True)
    (root / "conf").mkdir(parents=True, exist_ok=True)
    (root / "workspace" / "tasks" / "task-1" / "artifact.json").write_text("{}", encoding="utf-8")
    (root / "workspace" / "papers" / "paper.pdf").write_bytes(b"%PDF")
    (root / "conf" / "config.yaml").write_text("workspace_root: workspace/tasks\n", encoding="utf-8")
    (root / ".env").write_text("OPENAI_API_KEY=test\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='man1lab'\n", encoding="utf-8")
    (root / "README.md").write_text("# Man1Lab\n", encoding="utf-8")


class CleanupServiceTest(unittest.TestCase):
    def test_safe_cleanup_removes_regeneratable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = _test_settings(root)
            _seed_safe_artifacts(root)
            _seed_protected_artifacts(root)

            report = clean_workspace(settings, project_root=root)

            self.assertTrue(report.successful)
            self.assertEqual(report.policy, CleanPolicy.SAFE)
            self.assertFalse(report.dry_run)
            self.assertFalse((root / "outputs").exists())
            self.assertFalse((root / "logs").exists())
            self.assertFalse((root / "mlruns").exists())
            self.assertTrue((root / "workspace" / "tasks" / "task-1").exists())
            self.assertTrue((root / "workspace" / "papers" / "paper.pdf").exists())
            self.assertTrue((root / "conf" / "config.yaml").exists())
            self.assertTrue((root / ".env").exists())
            self.assertGreater(len(report.deleted_paths), 0)

    def test_all_cleanup_removes_tasks_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = _test_settings(root)
            _seed_safe_artifacts(root)
            _seed_protected_artifacts(root)
            (root / "workspace" / "artifacts").mkdir(parents=True, exist_ok=True)
            (root / "workspace" / "artifacts" / "strategy.json").write_text("{}", encoding="utf-8")

            report = clean_workspace(settings, policy=CleanPolicy.ALL, project_root=root)

            self.assertTrue(report.successful)
            self.assertEqual(report.policy, CleanPolicy.ALL)
            self.assertFalse((root / "workspace" / "tasks").exists())
            self.assertFalse((root / "workspace" / "artifacts").exists())
            self.assertTrue((root / "workspace" / "papers" / "paper.pdf").exists())

    def test_dry_run_reports_without_deleting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = _test_settings(root)
            _seed_safe_artifacts(root)

            report = clean_workspace(settings, dry_run=True, project_root=root)

            self.assertTrue(report.successful)
            self.assertTrue(report.dry_run)
            self.assertEqual(report.deleted_paths, [])
            self.assertGreater(len(report.planned_paths), 0)
            self.assertGreater(report.bytes_removed, 0)
            self.assertTrue((root / "outputs").exists())
            self.assertTrue((root / "logs").exists())

    def test_missing_directories_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = _test_settings(root)

            report = clean_workspace(settings, project_root=root)

            self.assertTrue(report.successful)
            self.assertGreater(len(report.missing_paths), 0)
            self.assertEqual(report.deleted_paths, [])

    def test_cleanup_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = _test_settings(root)
            _seed_safe_artifacts(root)

            first = clean_workspace(settings, project_root=root)
            second = clean_workspace(settings, project_root=root)

            self.assertTrue(first.successful)
            self.assertTrue(second.successful)
            self.assertGreater(len(first.deleted_paths), 0)
            self.assertEqual(second.deleted_paths, [])

    def test_protected_paths_are_never_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = _test_settings(root)
            _seed_protected_artifacts(root)

            clean_workspace(settings, policy=CleanPolicy.ALL, project_root=root)

            self.assertTrue((root / "conf" / "config.yaml").exists())
            self.assertTrue((root / ".env").exists())
            self.assertTrue((root / "workspace" / "papers" / "paper.pdf").exists())
            self.assertTrue((root / "pyproject.toml").exists())
            self.assertTrue((root / "README.md").exists())

    def test_cleanup_report_fields(self) -> None:
        report = CleanupReport(policy=CleanPolicy.SAFE, dry_run=True, successful=True)
        self.assertEqual(report.policy, CleanPolicy.SAFE)
        self.assertTrue(report.dry_run)
        self.assertTrue(report.successful)
        self.assertEqual(report.deleted_paths, [])
        self.assertEqual(report.errors, [])


class ProtectedPathTest(unittest.TestCase):
    def test_is_never_delete_for_conf_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertTrue(is_never_delete(root / "conf" / "config.yaml", root))
            self.assertTrue(is_never_delete(root / ".env", root))
            self.assertTrue(is_never_delete(root / "workspace" / "papers" / "paper.pdf", root))


class FacadeCleanupTest(unittest.TestCase):
    def test_facade_clean_delegates_to_lifecycle(self) -> None:
        from application import Man1Lab as Platform

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = _test_settings(root)
            _seed_safe_artifacts(root)

            platform = Platform(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            report = platform.clean(project_root=root)

            self.assertIsInstance(report, CleanupReport)
            self.assertTrue(report.successful)
            self.assertFalse((root / "outputs").exists())


class CLICleanupTest(unittest.TestCase):
    @patch("interfaces.cli.commands.clean.get_platform")
    def test_clean_command_delegates_to_facade(self, get_platform: MagicMock) -> None:
        get_platform.return_value.clean.return_value = CleanupReport(
            policy=CleanPolicy.SAFE,
            deleted_paths=[Path("outputs")],
            bytes_removed=128,
            successful=True,
        )
        result = runner.invoke(app, ["clean"])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.clean.assert_called_once_with(
            policy=CleanPolicy.SAFE,
            dry_run=False,
        )
        self.assertIn("Removed", result.stdout)

    @patch("interfaces.cli.commands.clean.get_platform")
    def test_clean_dry_run_presentation(self, get_platform: MagicMock) -> None:
        get_platform.return_value.clean.return_value = CleanupReport(
            policy=CleanPolicy.SAFE,
            planned_paths=[Path("outputs"), Path("logs"), Path("mlruns")],
            bytes_removed=4096,
            dry_run=True,
            successful=True,
        )
        result = runner.invoke(app, ["clean", "--dry-run"])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.clean.assert_called_once_with(
            policy=CleanPolicy.SAFE,
            dry_run=True,
        )
        self.assertIn("Will remove", result.stdout)
        self.assertIn("outputs", result.stdout)
        self.assertIn("Nothing deleted.", result.stdout)

    @patch("interfaces.cli.commands.clean.get_platform")
    def test_clean_all_delegates_with_policy(self, get_platform: MagicMock) -> None:
        get_platform.return_value.clean.return_value = CleanupReport(
            policy=CleanPolicy.ALL,
            deleted_paths=[Path("workspace/tasks")],
            successful=True,
        )
        result = runner.invoke(app, ["clean", "--all", "--yes"])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.clean.assert_called_once_with(
            policy=CleanPolicy.ALL,
            dry_run=False,
        )

    @patch("interfaces.cli.commands.clean.get_platform")
    def test_clean_all_requires_confirmation(self, get_platform: MagicMock) -> None:
        result = runner.invoke(app, ["clean", "--all"], input="n\n")
        self.assertNotEqual(result.exit_code, 0)
        get_platform.return_value.clean.assert_not_called()

    @patch("interfaces.cli.commands.clean.get_platform")
    def test_clean_all_skips_confirmation_with_yes(self, get_platform: MagicMock) -> None:
        get_platform.return_value.clean.return_value = CleanupReport(
            policy=CleanPolicy.ALL,
            successful=True,
        )
        result = runner.invoke(app, ["clean", "--all", "--yes"])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.clean.assert_called_once()


class SDKCleanupTest(unittest.TestCase):
    def test_sdk_clean_delegates_to_facade(self) -> None:
        from man1lab import Man1Lab

        with patch("application.facade.Man1Lab") as facade_cls:
            client = Man1Lab(initialize_configuration=False, configure_logging=False)
            expected = CleanupReport(policy=CleanPolicy.SAFE, successful=True)
            facade_cls.return_value.clean.return_value = expected

            report = client.clean(dry_run=True)

            facade_cls.return_value.clean.assert_called_once_with(
                policy=CleanPolicy.SAFE,
                dry_run=True,
                project_root=None,
            )
            self.assertIs(report, expected)


class LifecycleBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "agents",
        "discovery",
        "github",
        "llm",
    )

    def test_lifecycle_package_has_no_forbidden_imports(self) -> None:
        lifecycle_root = REPO_ROOT / "application" / "lifecycle"
        offenders: list[str] = []
        for path in lifecycle_root.rglob("*.py"):
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
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {module}")
                if module.startswith("configuration.hydra"):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {module}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
