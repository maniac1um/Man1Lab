"""Tests for the Man1Lab Python SDK."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from application import PLATFORM_VERSION
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
from man1lab import Man1Lab


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


class SDKImportTest(unittest.TestCase):
    def test_public_import_path(self) -> None:
        from man1lab import Man1Lab as PublicMan1Lab

        self.assertIs(PublicMan1Lab, Man1Lab)

    def test_interfaces_sdk_import_path(self) -> None:
        from interfaces.sdk import Man1Lab as SdkMan1Lab

        self.assertIs(SdkMan1Lab, Man1Lab)

    def test_package_version_matches_platform(self) -> None:
        import man1lab

        self.assertEqual(man1lab.__version__, PLATFORM_VERSION)


class SDKConstructionTest(unittest.TestCase):
    @patch("application.facade.Man1Lab")
    def test_construction_delegates_to_facade(self, facade_cls: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            client = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            facade_cls.assert_called_once()
            self.assertIs(client._facade, facade_cls.return_value)


class SDKDelegationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.facade = MagicMock()
        with patch("application.facade.Man1Lab", return_value=self.facade):
            self.client = Man1Lab(initialize_configuration=False, configure_logging=False)

    def test_reproduce_delegates(self) -> None:
        self.client.reproduce("paper.pdf")
        self.facade.reproduce.assert_called_once_with("paper.pdf")

    def test_analyze_delegates(self) -> None:
        self.client.analyze("paper.pdf")
        self.facade.analyze.assert_called_once_with("paper.pdf")

    def test_discover_delegates(self) -> None:
        analysis = MagicMock()
        self.client.discover(analysis)
        self.facade.discover.assert_called_once_with(analysis, paper_path=None)

    def test_plan_from_paper_delegates(self) -> None:
        self.client.plan(paper_path="paper.pdf")
        self.facade.plan_from_paper.assert_called_once_with("paper.pdf")

    def test_plan_with_artifacts_delegates(self) -> None:
        analysis = MagicMock()
        discovery = MagicMock()
        self.client.plan(analysis, discovery)
        self.facade.plan.assert_called_once_with(analysis, discovery)

    def test_execute_delegates(self) -> None:
        strategy = MagicMock()
        analysis = MagicMock()
        self.client.execute(strategy, analysis)
        self.facade.execute.assert_called_once_with(strategy, analysis)

    def test_execute_from_paths_delegates(self) -> None:
        self.client.execute(strategy_path="s.json", analysis_path="a.json")
        self.facade.execute_from_paths.assert_called_once_with("s.json", "a.json")

    def test_doctor_delegates(self) -> None:
        self.client.doctor()
        self.facade.doctor.assert_called_once()

    def test_version_delegates(self) -> None:
        self.facade.version.return_value = PLATFORM_VERSION
        self.assertEqual(self.client.version(), PLATFORM_VERSION)
        self.facade.version.assert_called_once()

    def test_configuration_delegates(self) -> None:
        expected = {"parser": {"backend": "pymupdf"}}
        self.facade.configuration.return_value = expected
        self.assertEqual(self.client.configuration(), expected)
        self.facade.configuration.assert_called_once()


class SDKIsolationTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = ("workflow", "interfaces.cli", "typer")

    def test_sdk_modules_do_not_import_workflow_or_cli(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sdk_root = repo_root / "src" / "interfaces" / "sdk"
        offenders: list[str] = []
        for path in sdk_root.rglob("*.py"):
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
                if root in self._FORBIDDEN_ROOTS or module.startswith("workflow"):
                    offenders.append(f"{path.relative_to(repo_root)}: {module}")
        self.assertEqual(offenders, [])

    def test_man1lab_package_reexports_sdk(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = (repo_root / "src" / "man1lab" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("from interfaces.sdk import", source)
        self.assertNotIn("workflow", source)


if __name__ == "__main__":
    unittest.main()
