"""Tests for runtime session subsystem."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
from runtime.lifecycle.errors import RuntimeNotReadyError
from runtime.profiling.report import RuntimeProfile, SessionProfileInfo
from runtime.profiling.timeline import RuntimeTimeline
from runtime.runtime import PlatformRuntime
from runtime.session import (
    RuntimeSession,
    SessionState,
    SessionTransitionError,
    SessionWorkspace,
)
from runtime.session.state import allowed_transitions, validate_transition
from runtime.state import RuntimeState

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


class SessionStateMachineTest(unittest.TestCase):
    def test_allowed_transitions(self) -> None:
        self.assertEqual(
            allowed_transitions(SessionState.NEW),
            frozenset({SessionState.ACTIVE}),
        )
        self.assertEqual(
            allowed_transitions(SessionState.ACTIVE),
            frozenset({SessionState.CLOSED}),
        )
        self.assertEqual(allowed_transitions(SessionState.CLOSED), frozenset())

    def test_validate_transition_rejects_invalid(self) -> None:
        with self.assertRaises(SessionTransitionError):
            validate_transition(SessionState.NEW, SessionState.CLOSED)

    def test_validate_transition_accepts_valid(self) -> None:
        validate_transition(SessionState.NEW, SessionState.ACTIVE)


class RuntimeSessionTest(unittest.TestCase):
    def test_starts_in_new_state(self) -> None:
        session = RuntimeSession()
        self.assertEqual(session.state, SessionState.NEW)
        self.assertFalse(session.is_active())

    def test_open_transitions_to_active(self) -> None:
        session = RuntimeSession()
        session.open()
        self.assertEqual(session.state, SessionState.ACTIVE)
        self.assertTrue(session.is_active())
        self.assertIsNotNone(session.duration_s())

    def test_close_transitions_to_closed(self) -> None:
        session = RuntimeSession()
        session.open()
        session.close()
        self.assertEqual(session.state, SessionState.CLOSED)
        self.assertFalse(session.is_active())
        self.assertIsNotNone(session.duration_s())

    def test_open_from_active_raises(self) -> None:
        session = RuntimeSession()
        session.open()
        with self.assertRaises(SessionTransitionError):
            session.open()

    def test_close_from_new_raises(self) -> None:
        session = RuntimeSession()
        with self.assertRaises(SessionTransitionError):
            session.close()

    def test_close_from_closed_raises(self) -> None:
        session = RuntimeSession()
        session.open()
        session.close()
        with self.assertRaises(SessionTransitionError):
            session.close()

    def test_workspace_placeholders_default_to_none(self) -> None:
        session = RuntimeSession()
        workspace = session.workspace
        self.assertIsInstance(workspace, SessionWorkspace)
        self.assertIsNone(workspace.workspace_root)
        self.assertIsNone(session.current_paper)
        self.assertIsNone(session.current_analysis)
        self.assertIsNone(session.current_discovery)
        self.assertIsNone(session.current_execution_strategy)

    def test_workspace_placeholders_are_mutable(self) -> None:
        session = RuntimeSession()
        paper = Path("paper.pdf")
        session.workspace.current_paper = paper
        session.workspace.current_analysis = {"title": "example"}
        self.assertIs(session.current_paper, paper)
        self.assertEqual(session.current_analysis, {"title": "example"})


class PlatformRuntimeSessionOwnershipTest(unittest.TestCase):
    def test_startup_creates_inactive_session(self) -> None:
        runtime = PlatformRuntime()
        runtime.startup()
        session = runtime.session
        self.assertIsInstance(session, RuntimeSession)
        self.assertEqual(session.state, SessionState.NEW)
        self.assertFalse(runtime.is_session_active())
        self.assertIs(runtime.context.session, session)

    def test_session_unavailable_before_startup(self) -> None:
        runtime = PlatformRuntime()
        with self.assertRaises(RuntimeNotReadyError):
            _ = runtime.session

    def test_close_session_delegates_to_session(self) -> None:
        runtime = PlatformRuntime()
        runtime.startup()
        runtime.session.open()
        runtime.close_session()
        self.assertEqual(runtime.session.state, SessionState.CLOSED)

    def test_shutdown_closes_active_session(self) -> None:
        runtime = PlatformRuntime()
        runtime.startup()
        runtime.session.open()
        runtime.shutdown()
        self.assertEqual(runtime.state, RuntimeState.STOPPED)
        with self.assertRaises(RuntimeNotReadyError):
            _ = runtime.session


class FacadeSessionDelegationTest(unittest.TestCase):
    def test_facade_exposes_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            session = platform.session()
            self.assertIsInstance(session, RuntimeSession)
            self.assertEqual(session.state, SessionState.NEW)
            self.assertFalse(platform.is_session_active())

    def test_facade_close_session_delegates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            platform.session().open()
            self.assertTrue(platform.is_session_active())
            platform.close_session()
            self.assertFalse(platform.is_session_active())
            self.assertEqual(platform.session().state, SessionState.CLOSED)

    def test_facade_behavior_unchanged_without_session_use(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            report = platform.list_models()
            self.assertIsNotNone(report)


class SessionProfilingIntegrationTest(unittest.TestCase):
    def test_profile_report_includes_session_metadata(self) -> None:
        profile = RuntimeProfile(
            timeline=RuntimeTimeline(stages=()),
            total_ms=1.0,
            session_info=SessionProfileInfo(state="ACTIVE", duration_s=2.5),
        )
        report = profile.format_report()
        self.assertIn("Session", report)
        self.assertIn("ACTIVE", report)
        self.assertIn("Duration", report)
        self.assertIn("2.5 s", report)

    def test_profile_report_includes_new_session_state(self) -> None:
        profile = RuntimeProfile(
            timeline=RuntimeTimeline(stages=()),
            total_ms=1.0,
            session_info=SessionProfileInfo(state="NEW"),
        )
        report = profile.format_report()
        self.assertIn("Session", report)
        self.assertIn("NEW", report)
        self.assertNotIn("Duration", report)

    def test_startup_profile_includes_session_state(self) -> None:
        profile = Man1Lab.profile_startup()
        self.assertIsNotNone(profile.session_info)
        self.assertEqual(profile.session_info.state, "NEW")


class RuntimeSessionBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "discovery",
        "agents",
        "providers",
    )

    def test_session_package_has_no_forbidden_imports(self) -> None:
        session_dir = REPO_ROOT / "runtime" / "session"
        offenders: list[str] = []
        for path in sorted(session_dir.glob("*.py")):
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


if __name__ == "__main__":
    unittest.main()
