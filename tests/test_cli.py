"""Tests for the Man1Lab CLI interface."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from application import PLATFORM_VERSION
from interfaces.cli.app import app
from interfaces.cli.common import EXIT_INVALID_ARGUMENTS, EXIT_PLATFORM_FAILURE
from tests.fixtures import create_sample_paper_pdf

runner = CliRunner()


class CLIHelpTest(unittest.TestCase):
    def test_root_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Man1Lab", result.stdout)
        self.assertIn("reproduce", result.stdout)
        self.assertIn("analyze", result.stdout)
        self.assertIn("init", result.stdout)
        self.assertIn("doctor", result.stdout)

    def test_command_help(self) -> None:
        result = runner.invoke(app, ["reproduce", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("complete reproduction workflow", result.stdout)


class CLIVersionTest(unittest.TestCase):
    def test_global_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout.strip(), PLATFORM_VERSION)

    @patch("interfaces.cli.commands.version.get_platform")
    def test_version_command_delegates_to_facade(self, get_platform: MagicMock) -> None:
        get_platform.return_value.version.return_value = "9.9.9"
        result = runner.invoke(app, ["version"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout.strip(), "9.9.9")
        get_platform.return_value.version.assert_called_once()


class CLIReproduceTest(unittest.TestCase):
    @patch("interfaces.cli.commands.reproduce.get_platform")
    def test_reproduce_delegates_to_facade(self, get_platform: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paper_path = Path(temp_dir) / "paper.pdf"
            create_sample_paper_pdf(paper_path)
            report = MagicMock()
            report.final_status = "SUCCESS"
            report.report_path = Path(temp_dir) / "report.md"
            get_platform.return_value.reproduce.return_value = report

            result = runner.invoke(app, ["reproduce", str(paper_path)])

        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.reproduce.assert_called_once()
        self.assertIn("SUCCESS", result.stdout)

    def test_reproduce_missing_paper_exits_invalid_arguments(self) -> None:
        result = runner.invoke(app, ["reproduce", "/tmp/does-not-exist.pdf"])
        self.assertEqual(result.exit_code, EXIT_INVALID_ARGUMENTS)
        combined = result.stdout + result.stderr
        self.assertIn("Error:", combined)


class CLIAnalyzeTest(unittest.TestCase):
    @patch("interfaces.cli.commands.analyze.get_platform")
    def test_analyze_delegates_to_facade(self, get_platform: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paper_path = Path(temp_dir) / "paper.pdf"
            create_sample_paper_pdf(paper_path)
            analysis = MagicMock()
            analysis.model_dump_json.return_value = '{"metadata":{"title":"T"}}'
            get_platform.return_value.analyze.return_value = analysis

            result = runner.invoke(app, ["analyze", str(paper_path)])

        self.assertEqual(result.exit_code, 0)
        get_platform.return_value.analyze.assert_called_once()


class CLIDoctorTest(unittest.TestCase):
    @patch("interfaces.cli.commands.doctor.get_platform")
    def test_doctor_success(self, get_platform: MagicMock) -> None:
        from application.facade import DoctorCheck, DoctorReport

        get_platform.return_value.doctor.return_value = DoctorReport(
            healthy=True,
            checks=[DoctorCheck(name="workspace_root", status="ok", message="ready")],
        )
        result = runner.invoke(app, ["doctor"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("✓ workspace", result.stdout)
        self.assertIn("Environment check passed", result.stdout)

    @patch("interfaces.cli.commands.doctor.get_platform")
    def test_doctor_failure_exits_platform_failure(self, get_platform: MagicMock) -> None:
        from application.facade import DoctorCheck, DoctorReport

        get_platform.return_value.doctor.return_value = DoctorReport(
            healthy=False,
            checks=[DoctorCheck(name="prompts_dir", status="fail", message="missing")],
        )
        result = runner.invoke(app, ["doctor"])
        self.assertEqual(result.exit_code, EXIT_PLATFORM_FAILURE)


class CLIConfigTest(unittest.TestCase):
    @patch("interfaces.cli.commands.config.get_platform")
    def test_config_delegates_to_facade(self, get_platform: MagicMock) -> None:
        get_platform.return_value.configuration.return_value = {
            "parser": {"backend": "pymupdf"},
            "discovery": {"enabled": True},
        }
        result = runner.invoke(app, ["config"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("pymupdf", result.stdout)


class CLIWorkflowIsolationTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "agents",
        "discovery",
        "execution_planning",
        "tracking",
        "hydra",
        "configuration",
    )

    def test_cli_modules_do_not_import_workflow_or_capabilities(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        cli_root = repo_root / "interfaces" / "cli"
        offenders: list[str] = []
        for path in cli_root.rglob("*.py"):
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
                    offenders.append(f"{path.relative_to(repo_root)}: {module}")
        self.assertEqual(offenders, [])

    def test_cli_imports_application_facade(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        common_source = (repo_root / "interfaces" / "cli" / "common.py").read_text(encoding="utf-8")
        self.assertIn("from application import Man1Lab", common_source)


if __name__ == "__main__":
    unittest.main()
