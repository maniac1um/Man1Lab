"""Tests for runtime profiling subsystem."""

from __future__ import annotations

import ast
import re
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from application.facade import Man1Lab
from interfaces.cli.app import app
from runtime.profiling import RuntimeProfiler, RuntimeProfile, StageMeasurement
from runtime.profiling.profiler import RuntimeProfiler as ProfilerClass

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]


class RuntimeProfilerTest(unittest.TestCase):
    def test_measure_records_stage(self) -> None:
        profiler = RuntimeProfiler()
        with profiler.measure("Import"):
            time.sleep(0.001)
        profile = profiler.build_profile()
        self.assertEqual(len(profile.stages), 1)
        self.assertEqual(profile.stages[0].name, "Import")
        self.assertGreater(profile.stages[0].duration_ms, 0.0)

    def test_begin_and_end_stage(self) -> None:
        profiler = RuntimeProfiler()
        profiler.begin_stage("Configuration")
        measurement = profiler.end_stage()
        self.assertEqual(measurement.name, "Configuration")
        self.assertGreaterEqual(measurement.duration_ms, 0.0)

    def test_nested_stages(self) -> None:
        profiler = RuntimeProfiler()
        profiler.begin_stage("Facade")
        profiler.begin_stage("Workflow")
        inner = profiler.end_stage()
        outer = profiler.end_stage()
        self.assertEqual(inner.name, "Workflow")
        self.assertEqual(outer.name, "Facade")
        self.assertEqual(len(outer.children), 1)
        self.assertEqual(outer.children[0].name, "Workflow")

    def test_measurement_ordering_is_deterministic(self) -> None:
        profiler = RuntimeProfiler()
        with profiler.measure("Import"):
            pass
        with profiler.measure("Configuration"):
            pass
        with profiler.measure("Facade"):
            pass
        stages = profiler.build_profile().stages
        self.assertEqual([stage.name for stage in stages], ["Import", "Configuration", "Facade"])
        self.assertEqual([stage.order for stage in stages], [1, 2, 3])

    def test_end_stage_without_begin_raises(self) -> None:
        profiler = RuntimeProfiler()
        with self.assertRaises(RuntimeError):
            profiler.end_stage()

    def test_total_includes_wall_clock(self) -> None:
        profiler = RuntimeProfiler()
        with profiler.measure("Import"):
            time.sleep(0.002)
        profile = profiler.build_profile()
        self.assertGreaterEqual(profile.total_ms, profile.stages[0].duration_ms)

    def test_flattened_measurements(self) -> None:
        profiler = RuntimeProfiler()
        profiler.begin_stage("Facade")
        profiler.begin_stage("Workflow")
        profiler.end_stage()
        profiler.end_stage()
        flattened = profiler.build_timeline().flattened()
        self.assertEqual([stage.name for stage in flattened], ["Facade", "Workflow"])


class RuntimeReportTest(unittest.TestCase):
    def test_format_report_contains_expected_sections(self) -> None:
        profiler = RuntimeProfiler()
        with profiler.measure("Import"):
            pass
        with profiler.measure("Configuration"):
            pass
        report = profiler.build_profile().format_report()
        self.assertIn("Runtime Profile", report)
        self.assertIn("Import", report)
        self.assertIn("Configuration", report)
        self.assertIn("Total", report)
        self.assertRegex(report, r"\d+\.\d ms")

    def test_format_report_is_deterministic(self) -> None:
        profiler = RuntimeProfiler()

        def _build() -> str:
            local = RuntimeProfiler()
            with local.measure("Import"):
                pass
            with local.measure("Configuration"):
                pass
            return local.build_profile().format_report()

        first = _build()
        second = _build()
        self.assertEqual(
            re.sub(r"\d+\.\d", "X", first),
            re.sub(r"\d+\.\d", "X", second),
        )


class FacadeProfileStartupTest(unittest.TestCase):
    def test_facade_profile_startup_returns_profile(self) -> None:
        profile = Man1Lab.profile_startup()
        self.assertIsInstance(profile, RuntimeProfile)
        names = [stage.name for stage in profile.stages]
        self.assertEqual(names, ["Import", "Configuration", "Facade", "Workflow"])

    def test_stage_durations_are_non_negative(self) -> None:
        profile = Man1Lab.profile_startup()
        for stage in profile.timeline.flattened():
            self.assertGreaterEqual(stage.duration_ms, 0.0)


class ProfileCLITest(unittest.TestCase):
    def test_profile_command_output(self) -> None:
        result = runner.invoke(app, ["profile"])
        self.assertEqual(result.exit_code, 0, msg=result.stdout + result.stderr)
        self.assertIn("Runtime Profile", result.stdout)
        self.assertIn("Import", result.stdout)
        self.assertIn("Configuration", result.stdout)
        self.assertIn("Facade", result.stdout)
        self.assertIn("Workflow", result.stdout)
        self.assertIn("Total", result.stdout)
        self.assertIn("Runtime Resources", result.stdout)
        self.assertIn("READY", result.stdout)
        self.assertIn("DEFERRED", result.stdout)
        self.assertIn("Session", result.stdout)
        self.assertIn("NEW", result.stdout)

    @patch("interfaces.cli.commands.profile.Man1Lab.profile_startup")
    def test_profile_delegates_to_facade(self, profile_startup) -> None:
        from runtime.profiling.timeline import RuntimeTimeline
        from runtime.profiling.report import RuntimeProfile
        from runtime.profiling.measurements import StageMeasurement

        profile_startup.return_value = RuntimeProfile(
            timeline=RuntimeTimeline(
                stages=(
                    StageMeasurement(name="Import", duration_ms=1.0, order=1),
                )
            ),
            total_ms=1.0,
        )
        result = runner.invoke(app, ["profile"])
        self.assertEqual(result.exit_code, 0)
        profile_startup.assert_called_once()


class RuntimeProfilingBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "discovery",
        "agents",
        "providers",
        "interfaces",
    )

    def test_runtime_profiling_has_no_forbidden_imports(self) -> None:
        profiling_root = REPO_ROOT / "runtime" / "profiling"
        offenders: list[str] = []
        for path in profiling_root.rglob("*.py"):
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
        self.assertEqual(offenders, [])

    def test_profiler_has_no_global_singleton(self) -> None:
        first = RuntimeProfiler()
        second = RuntimeProfiler()
        self.assertIsNot(first, second)
        self.assertFalse(hasattr(ProfilerClass, "_instance"))


if __name__ == "__main__":
    unittest.main()
