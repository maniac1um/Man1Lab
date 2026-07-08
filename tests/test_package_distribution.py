"""Tests for Man1Lab package distribution and lifecycle commands."""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

import man1lab
from application import PLATFORM_VERSION
from application.lifecycle import init_workspace, run_doctor_checks
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
from interfaces.cli.app import app, run_cli
from man1lab import Man1Lab, PLATFORM_VERSION as SDK_PLATFORM_VERSION, __version__

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]


def _test_settings(temp_dir: Path) -> AppSettings:
    return AppSettings(
        workspace_root=temp_dir / "workspace",
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


class PackageImportTest(unittest.TestCase):
    def test_public_package_exports(self) -> None:
        self.assertEqual(set(man1lab.__all__), {"PLATFORM_VERSION", "DoctorReport", "ExecuteResult", "Man1Lab"})
        self.assertIsNotNone(Man1Lab)

    def test_version_consistency(self) -> None:
        self.assertEqual(__version__, PLATFORM_VERSION)
        self.assertEqual(SDK_PLATFORM_VERSION, PLATFORM_VERSION)
        self.assertEqual(man1lab.__version__, PLATFORM_VERSION)

    def test_no_workflow_exports_from_public_package(self) -> None:
        public_names = {name for name in dir(man1lab) if not name.startswith("_")}
        forbidden = {"WorkflowOrchestrator", "Reader", "Planner", "Coder"}
        self.assertTrue(forbidden.isdisjoint(public_names))


class ConsoleEntryTest(unittest.TestCase):
    def test_run_cli_entry_point_exists(self) -> None:
        self.assertTrue(callable(run_cli))

    def test_module_main_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("init", result.stdout)
        self.assertIn("clean", result.stdout)

    def test_python_module_main(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "man1lab", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Man1Lab", result.stdout)


class LifecycleCommandTest(unittest.TestCase):
    @patch("interfaces.cli.commands.init.get_platform")
    def test_init_command_delegates_to_facade(self, get_platform: MagicMock) -> None:
        from application.lifecycle import InitAction, InitReport

        get_platform.return_value.init.return_value = InitReport(
            successful=True,
            actions=[InitAction(path=Path("."), action="ready", message="ok")],
            next_steps=["Run doctor"],
        )
        result = runner.invoke(app, ["init"])
        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.init.assert_called_once()
        self.assertIn("Next steps", result.stdout)

    def test_init_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = _test_settings(root)
            env_path = root / ".env"
            env_path.write_text("OPENAI_API_KEY=existing\n", encoding="utf-8")

            first = init_workspace(settings, workspace_root=root)
            second = init_workspace(settings, workspace_root=root)

            self.assertTrue(first.successful)
            self.assertTrue(second.successful)
            self.assertEqual(env_path.read_text(encoding="utf-8"), "OPENAI_API_KEY=existing\n")
            skipped = [action for action in second.actions if action.action == "skipped"]
            self.assertTrue(any(".env" in str(action.path) for action in skipped))

    def test_doctor_success_via_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            report = run_doctor_checks(settings)
            self.assertTrue(report.healthy)
            names = {check.name for check in report.checks}
            self.assertIn("Python", names)
            self.assertIn("Package Version", names)

    @patch("interfaces.cli.commands.doctor.get_platform")
    def test_doctor_command_success(self, get_platform: MagicMock) -> None:
        from application.lifecycle import DoctorCheck, DoctorReport

        get_platform.return_value.doctor.return_value = DoctorReport(
            healthy=True,
            checks=[DoctorCheck(name="Python", status="ok", message="3.12")],
        )
        result = runner.invoke(app, ["doctor"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("✓ Python", result.stdout)


class PackageMetadataTest(unittest.TestCase):
    def test_pyproject_exists(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('name = "man1lab"', pyproject)
        self.assertIn('man1lab = "interfaces.cli.app:run_cli"', pyproject)

    def test_manifest_includes_resources(self) -> None:
        manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("recursive-include conf", manifest)
        self.assertIn(".env.example", manifest)


class PackageIsolationTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = ("workflow", "agents", "discovery", "execution_planning")

    def test_man1lab_package_does_not_import_workflow(self) -> None:
        package_root = REPO_ROOT / "man1lab"
        offenders: list[str] = []
        for path in package_root.rglob("*.py"):
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

    def test_man1lab_main_delegates_to_cli(self) -> None:
        source = (REPO_ROOT / "man1lab" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("interfaces.cli.app", source)


class FacadeLifecycleTest(unittest.TestCase):
    def test_facade_init_and_doctor(self) -> None:
        from application import Man1Lab as Platform

        with tempfile.TemporaryDirectory() as temp_dir:
            platform = Platform(
                settings=_test_settings(Path(temp_dir)),
                initialize_configuration=False,
                configure_logging=False,
            )
            init_report = platform.init(workspace_root=Path(temp_dir))
            doctor_report = platform.doctor()
            self.assertTrue(init_report.successful)
            self.assertTrue(doctor_report.healthy)


if __name__ == "__main__":
    unittest.main()
