"""Tests for runtime lazy initialization."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from application import Man1Lab
from application.runtime.resource_wiring import wire_runtime_resources
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
from prompt.loader import PromptLoader
from providers.llm.manager import LLMManager
from providers.llm.provider_registry import ProviderRegistry
from runtime.context import RuntimeContext
from runtime.lazy import LazyResource, LazyValue, ResourceRegistry
from runtime.resources import RuntimeResourceManager
from runtime.lazy.resource_registry import (
    RESOURCE_CONFIGURATION,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROMPT_REGISTRY,
    RESOURCE_PROVIDER_REGISTRY,
)
from runtime.profiling.report import RuntimeProfile
from runtime.profiling.timeline import RuntimeTimeline
from runtime.runtime import PlatformRuntime

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


class LazyValueTest(unittest.TestCase):
    def test_initializes_once(self) -> None:
        factory = MagicMock(return_value=42)
        lazy = LazyValue(factory)

        self.assertFalse(lazy.is_initialized())
        self.assertEqual(lazy.status, "deferred")
        self.assertEqual(lazy.get(), 42)
        self.assertEqual(lazy.get(), 42)
        factory.assert_called_once()

    def test_reuses_instance_on_multiple_accesses(self) -> None:
        sentinel = object()
        lazy = LazyValue(lambda: sentinel)
        self.assertIs(lazy.get(), lazy.get())

    def test_propagates_initialization_errors(self) -> None:
        lazy = LazyValue(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

        with self.assertRaisesRegex(RuntimeError, "boom"):
            lazy.get()
        with self.assertRaisesRegex(RuntimeError, "boom"):
            lazy.get()

    def test_status_becomes_initialized(self) -> None:
        lazy = LazyValue(lambda: "ready")
        lazy.get()
        self.assertTrue(lazy.is_initialized())
        self.assertEqual(lazy.status, "initialized")


class LazyResourceTest(unittest.TestCase):
    def test_carries_name(self) -> None:
        resource = LazyResource("configuration", lambda: "value")
        self.assertEqual(resource.name, "configuration")
        self.assertEqual(resource.get(), "value")


class ResourceRegistryTest(unittest.TestCase):
    def test_register_and_get(self) -> None:
        registry = ResourceRegistry()
        registry.register("configuration", lambda: {"enabled": True})
        self.assertEqual(registry.get("configuration"), {"enabled": True})

    def test_rejects_duplicate_registration(self) -> None:
        registry = ResourceRegistry()
        registry.register("configuration", lambda: 1)
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register("configuration", lambda: 2)

    def test_status_entries_reflect_initialization(self) -> None:
        registry = ResourceRegistry()
        registry.register(RESOURCE_CONFIGURATION, lambda: "config")
        registry.register(RESOURCE_PROMPT_REGISTRY, lambda: "prompt")
        registry.register(RESOURCE_LLM_MANAGER, lambda: "llm")
        registry.register(RESOURCE_PROVIDER_REGISTRY, lambda: "provider")

        registry.get(RESOURCE_CONFIGURATION)
        statuses = dict(registry.status_entries())
        self.assertEqual(statuses["Configuration"], "initialized")
        self.assertEqual(statuses["Prompt Registry"], "deferred")
        self.assertEqual(statuses["LLM Manager"], "deferred")
        self.assertEqual(statuses["Provider Registry"], "deferred")


class RuntimeContextLazyTest(unittest.TestCase):
    def test_create_starts_with_empty_manager(self) -> None:
        context = RuntimeContext.create()
        self.assertIsInstance(context.resource_manager, RuntimeResourceManager)
        self.assertIsNone(context.workspace)
        self.assertIsNone(context.session)

    def test_exposes_lazy_resources_after_wiring(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            context = RuntimeContext.create()
            wire_runtime_resources(context.resource_manager, settings=settings, initialize_configuration=False)

            self.assertFalse(context.configuration.is_initialized())
            self.assertIsInstance(context.configuration, LazyResource)
            self.assertIsInstance(context.prompt_registry, LazyResource)
            self.assertIsInstance(context.llm_manager, LazyResource)

    def test_resource_status_entries_after_partial_init(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            context = RuntimeContext.create()
            wire_runtime_resources(context.resource_manager, settings=settings, initialize_configuration=False)
            context.configuration.get()

            statuses = dict(context.resource_status_entries())
            self.assertEqual(statuses["Configuration"], "READY (Runtime Cache)")
            self.assertEqual(statuses["Prompt Registry"], "DEFERRED")


class ResourceWiringTest(unittest.TestCase):
    def test_wiring_creates_expected_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            manager = RuntimeResourceManager()
            wire_runtime_resources(manager, settings=settings, initialize_configuration=False)

            self.assertIs(manager.get(RESOURCE_CONFIGURATION), settings)
            self.assertIsInstance(manager.get(RESOURCE_PROMPT_REGISTRY), PromptLoader)
            self.assertIsInstance(manager.get(RESOURCE_PROVIDER_REGISTRY), ProviderRegistry)
            self.assertIsInstance(manager.get(RESOURCE_LLM_MANAGER), LLMManager)

    def test_llm_manager_reuses_provider_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            manager = RuntimeResourceManager()
            wire_runtime_resources(manager, settings=settings, initialize_configuration=False)

            provider_registry = manager.get(RESOURCE_PROVIDER_REGISTRY)
            llm_manager = manager.get(RESOURCE_LLM_MANAGER)
            self.assertIs(llm_manager._provider_registry, provider_registry)  # noqa: SLF001


class ProfilingIntegrationTest(unittest.TestCase):
    def test_profile_report_includes_resource_statuses(self) -> None:
        profile = RuntimeProfile(
            timeline=RuntimeTimeline(stages=()),
            total_ms=1.0,
            resource_statuses=(
                ("Configuration", "READY (Runtime Cache)"),
                ("LLM Manager", "DEFERRED"),
                ("Prompt Registry", "DEFERRED"),
            ),
        )
        report = profile.format_report()
        self.assertIn("Runtime Resources", report)
        self.assertIn("Configuration", report)
        self.assertIn("READY (Runtime Cache)", report)
        self.assertIn("LLM Manager", report)
        self.assertIn("DEFERRED", report)

    def test_startup_profile_collects_resource_statuses(self) -> None:
        profile = Man1Lab.profile_startup()
        self.assertTrue(profile.resource_statuses)
        statuses = dict(profile.resource_statuses)
        self.assertEqual(statuses["Configuration"], "READY (Runtime Cache)")
        self.assertEqual(statuses["Prompt Registry"], "DEFERRED")


class FacadeLazyBehaviorTest(unittest.TestCase):
    def test_facade_initializes_configuration_and_llm_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            context = platform.runtime.context
            self.assertTrue(context.configuration.is_initialized())
            self.assertTrue(context.llm_manager.is_initialized())
            self.assertFalse(context.prompt_registry.is_initialized())

    def test_model_operations_still_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            report = platform.list_models()
            self.assertIsNotNone(report)


class RuntimeLazyBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "discovery",
        "agents",
        "providers",
    )

    def test_lazy_package_has_no_forbidden_imports(self) -> None:
        lazy_dir = REPO_ROOT / "runtime" / "lazy"
        offenders: list[str] = []
        for path in sorted(lazy_dir.glob("*.py")):
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

    def test_no_global_singleton_in_lazy_package(self) -> None:
        lazy_init = (REPO_ROOT / "runtime" / "lazy" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("singleton", lazy_init.lower())


class RuntimeLifecycleLazyIntegrationTest(unittest.TestCase):
    def test_platform_runtime_startup_provides_manager(self) -> None:
        runtime = PlatformRuntime()
        context = runtime.startup()
        self.assertIsInstance(context.resource_manager, RuntimeResourceManager)


if __name__ == "__main__":
    unittest.main()
