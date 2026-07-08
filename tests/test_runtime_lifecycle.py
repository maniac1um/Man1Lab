"""Tests for platform runtime lifecycle."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from application import Man1Lab
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
from runtime.context import RuntimeContext
from runtime.resources import RuntimeResourceManager
from runtime.session import RuntimeSession, SessionState
from runtime.lifecycle.errors import RuntimeNotReadyError, RuntimeTransitionError
from runtime.runtime import PlatformRuntime
from runtime.state import RuntimeState, allowed_transitions, validate_transition

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


class RuntimeStateMachineTest(unittest.TestCase):
    def test_allowed_transitions(self) -> None:
        self.assertEqual(
            allowed_transitions(RuntimeState.NEW),
            frozenset({RuntimeState.BOOTSTRAPPING}),
        )
        self.assertEqual(
            allowed_transitions(RuntimeState.READY),
            frozenset({RuntimeState.SHUTTING_DOWN}),
        )
        self.assertEqual(allowed_transitions(RuntimeState.STOPPED), frozenset())

    def test_validate_transition_rejects_invalid(self) -> None:
        with self.assertRaises(RuntimeTransitionError):
            validate_transition(RuntimeState.NEW, RuntimeState.READY)

    def test_validate_transition_accepts_valid(self) -> None:
        validate_transition(RuntimeState.NEW, RuntimeState.BOOTSTRAPPING)


class PlatformRuntimeTest(unittest.TestCase):
    def test_startup_transitions_to_ready(self) -> None:
        runtime = PlatformRuntime()
        context = runtime.startup()
        self.assertEqual(runtime.state, RuntimeState.READY)
        self.assertIsInstance(context, RuntimeContext)
        self.assertTrue(runtime.is_ready())
        self.assertIsInstance(runtime.session, RuntimeSession)
        self.assertEqual(runtime.session.state, SessionState.NEW)

    def test_shutdown_transitions_to_stopped(self) -> None:
        runtime = PlatformRuntime()
        runtime.startup()
        runtime.shutdown()
        self.assertEqual(runtime.state, RuntimeState.STOPPED)
        self.assertFalse(runtime.is_ready())

    def test_startup_from_non_new_raises(self) -> None:
        runtime = PlatformRuntime()
        runtime.startup()
        with self.assertRaises(RuntimeTransitionError):
            runtime.startup()

    def test_shutdown_before_ready_raises(self) -> None:
        runtime = PlatformRuntime()
        with self.assertRaises(RuntimeTransitionError):
            runtime.shutdown()

    def test_shutdown_twice_raises(self) -> None:
        runtime = PlatformRuntime()
        runtime.startup()
        runtime.shutdown()
        with self.assertRaises(RuntimeTransitionError):
            runtime.shutdown()

    def test_context_unavailable_before_startup(self) -> None:
        runtime = PlatformRuntime()
        with self.assertRaises(RuntimeNotReadyError):
            _ = runtime.context

    def test_context_unavailable_after_shutdown(self) -> None:
        runtime = PlatformRuntime()
        runtime.startup()
        runtime.shutdown()
        with self.assertRaises(RuntimeNotReadyError):
            _ = runtime.context

    def test_no_singleton_instances(self) -> None:
        first = PlatformRuntime()
        second = PlatformRuntime()
        self.assertIsNot(first, second)


class RuntimeContextTest(unittest.TestCase):
    def test_create_returns_empty_manager(self) -> None:
        context = RuntimeContext.create()
        self.assertIsInstance(context.resource_manager, RuntimeResourceManager)
        self.assertIs(context.resources, context.resource_manager)
        self.assertIsNone(context.workspace)
        self.assertIsNone(context.session)
        with self.assertRaises(KeyError):
            _ = context.configuration

    def test_startup_wires_session_on_context(self) -> None:
        runtime = PlatformRuntime()
        context = runtime.startup()
        self.assertIsInstance(context.session, RuntimeSession)
        self.assertIs(context.session, runtime.session)
        self.assertEqual(context.session.state, SessionState.NEW)

    def test_wired_resources_are_lazy_until_accessed(self) -> None:
        from application.runtime.resource_wiring import wire_runtime_resources

        context = RuntimeContext.create()
        wire_runtime_resources(context.resource_manager, initialize_configuration=False)
        self.assertFalse(context.configuration.is_initialized())
        self.assertFalse(context.prompt_registry.is_initialized())


class FacadeRuntimeDelegationTest(unittest.TestCase):
    def test_facade_starts_provided_runtime(self) -> None:
        import tempfile

        runtime = PlatformRuntime()
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
                runtime=runtime,
            )
        self.assertIs(platform.runtime, runtime)
        self.assertTrue(platform.is_runtime_ready())

    def test_facade_creates_runtime_when_not_provided(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
        self.assertEqual(platform.runtime.state, RuntimeState.READY)
        self.assertTrue(platform.is_runtime_ready())

    def test_facade_shutdown_delegates_to_runtime(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            self.assertTrue(platform.is_runtime_ready())
            platform.shutdown_runtime()
            self.assertEqual(platform.runtime.state, RuntimeState.STOPPED)

    @patch("application.runtime.startup_profile.profile_platform_startup")
    def test_profile_startup_still_delegates(self, profile_startup: MagicMock) -> None:
        from runtime.profiling.timeline import RuntimeTimeline
        from runtime.profiling.report import RuntimeProfile
        from runtime.profiling.measurements import StageMeasurement

        profile_startup.return_value = RuntimeProfile(
            timeline=RuntimeTimeline(stages=()),
            total_ms=0.0,
        )
        Man1Lab.profile_startup()
        profile_startup.assert_called_once()


class RuntimeLifecycleBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "discovery",
        "agents",
        "providers",
        "interfaces",
    )

    def test_runtime_core_has_no_forbidden_imports(self) -> None:
        paths = [
            REPO_ROOT / "runtime" / "runtime.py",
            REPO_ROOT / "runtime" / "state.py",
            REPO_ROOT / "runtime" / "context.py",
            REPO_ROOT / "runtime" / "lifecycle" / "errors.py",
            *sorted((REPO_ROOT / "runtime" / "lazy").glob("*.py")),
            *sorted((REPO_ROOT / "runtime" / "resources").glob("*.py")),
            *sorted((REPO_ROOT / "runtime" / "session").glob("*.py")),
        ]
        offenders: list[str] = []
        for path in paths:
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

    def test_profiling_remains_independent(self) -> None:
        profiling_init = REPO_ROOT / "runtime" / "profiling" / "__init__.py"
        source = profiling_init.read_text(encoding="utf-8")
        self.assertNotIn("lifecycle", source)
        self.assertNotIn("PlatformRuntime", source)


if __name__ == "__main__":
    unittest.main()
