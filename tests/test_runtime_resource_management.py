"""Tests for runtime resource management."""

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
from runtime.profiling.report import RuntimeProfile
from runtime.profiling.timeline import RuntimeTimeline
from runtime.resources import (
    CachePolicy,
    RuntimeResourceDescriptor,
    RuntimeResourceHealth,
    RuntimeResourceManager,
)
from runtime.resources.manager import (
    RESOURCE_CONFIGURATION,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROMPT_REGISTRY,
    RESOURCE_PROVIDER_REGISTRY,
)

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


class RuntimeResourceManagerTest(unittest.TestCase):
    def test_register_and_resolve(self) -> None:
        manager = RuntimeResourceManager()
        manager.register(
            "configuration",
            lambda: {"enabled": True},
            resource_type="configuration",
            cache_policy=CachePolicy.RUNTIME,
        )
        self.assertEqual(manager.get("configuration"), {"enabled": True})

    def test_rejects_duplicate_registration(self) -> None:
        manager = RuntimeResourceManager()
        manager.register("configuration", lambda: 1, resource_type="configuration")
        with self.assertRaisesRegex(ValueError, "already registered"):
            manager.register("configuration", lambda: 2, resource_type="configuration")

    def test_descriptor_reflects_metadata(self) -> None:
        manager = RuntimeResourceManager()
        manager.register(
            "configuration",
            lambda: "value",
            resource_type="configuration",
            lazy=True,
            cache_policy=CachePolicy.SESSION,
        )
        descriptor = manager.descriptor("configuration")
        self.assertIsInstance(descriptor, RuntimeResourceDescriptor)
        self.assertEqual(descriptor.name, "configuration")
        self.assertEqual(descriptor.resource_type, "configuration")
        self.assertTrue(descriptor.lazy)
        self.assertFalse(descriptor.initialized)
        self.assertEqual(descriptor.cache_policy, CachePolicy.SESSION)
        self.assertEqual(descriptor.health, RuntimeResourceHealth.DEFERRED)
        self.assertEqual(descriptor.access_count, 0)
        self.assertIsNone(descriptor.last_accessed)

    def test_health_transitions_deferred_to_ready(self) -> None:
        manager = RuntimeResourceManager()
        manager.register("configuration", lambda: "ready", resource_type="configuration")
        self.assertEqual(manager.descriptor("configuration").health, RuntimeResourceHealth.DEFERRED)
        manager.get("configuration")
        self.assertEqual(manager.descriptor("configuration").health, RuntimeResourceHealth.READY)
        self.assertTrue(manager.descriptor("configuration").initialized)

    def test_health_transitions_to_failed(self) -> None:
        manager = RuntimeResourceManager()
        manager.register(
            "configuration",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            resource_type="configuration",
        )
        with self.assertRaisesRegex(RuntimeError, "boom"):
            manager.get("configuration")
        self.assertEqual(manager.descriptor("configuration").health, RuntimeResourceHealth.FAILED)

    def test_access_count_increments(self) -> None:
        manager = RuntimeResourceManager()
        manager.register("configuration", lambda: object(), resource_type="configuration")
        manager.get("configuration")
        manager.get("configuration")
        descriptor = manager.descriptor("configuration")
        self.assertEqual(descriptor.access_count, 2)
        self.assertIsNotNone(descriptor.last_accessed)

    def test_statistics_aggregate_counts(self) -> None:
        manager = RuntimeResourceManager()
        manager.register("configuration", lambda: 1, resource_type="configuration")
        manager.register("prompt_registry", lambda: 2, resource_type="prompt_registry")
        manager.get("configuration")
        stats = manager.statistics()
        self.assertEqual(stats.total_resources, 2)
        self.assertEqual(stats.initialized_count, 1)
        self.assertEqual(stats.deferred_count, 1)
        self.assertEqual(stats.ready_count, 1)
        self.assertEqual(stats.failed_count, 0)
        self.assertEqual(stats.total_access_count, 1)

    def test_profile_entries_include_health_and_cache(self) -> None:
        manager = RuntimeResourceManager()
        manager.register(
            RESOURCE_CONFIGURATION,
            lambda: "config",
            resource_type="configuration",
            cache_policy=CachePolicy.RUNTIME,
        )
        manager.register(
            RESOURCE_PROMPT_REGISTRY,
            lambda: "prompt",
            resource_type="prompt_registry",
            cache_policy=CachePolicy.RUNTIME,
        )
        manager.get(RESOURCE_CONFIGURATION)
        entries = dict(manager.profile_entries())
        self.assertEqual(entries["Configuration"], "READY (Runtime Cache)")
        self.assertEqual(entries["Prompt Registry"], "DEFERRED")

    def test_lazy_reuse_through_manager(self) -> None:
        factory = MagicMock(return_value=object())
        manager = RuntimeResourceManager()
        manager.register("configuration", factory, resource_type="configuration")
        first = manager.get("configuration")
        second = manager.get("configuration")
        self.assertIs(first, second)
        factory.assert_called_once()


class RuntimeContextResourceManagerTest(unittest.TestCase):
    def test_create_owns_resource_manager(self) -> None:
        context = RuntimeContext.create()
        self.assertIsInstance(context.resource_manager, RuntimeResourceManager)
        self.assertIs(context.resources, context.resource_manager)

    def test_wired_resources_expose_lazy_handles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            context = RuntimeContext.create()
            wire_runtime_resources(context.resource_manager, settings=settings, initialize_configuration=False)
            self.assertFalse(context.configuration.is_initialized())
            self.assertFalse(context.prompt_registry.is_initialized())

    def test_resource_status_entries_use_manager_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            context = RuntimeContext.create()
            wire_runtime_resources(context.resource_manager, settings=settings, initialize_configuration=False)
            context.resource_manager.get(RESOURCE_CONFIGURATION)
            statuses = dict(context.resource_status_entries())
            self.assertEqual(statuses["Configuration"], "READY (Runtime Cache)")
            self.assertEqual(statuses["Prompt Registry"], "DEFERRED")


class ResourceWiringManagerTest(unittest.TestCase):
    def test_wiring_registers_expected_types(self) -> None:
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


class ProfilingResourceMetadataTest(unittest.TestCase):
    def test_profile_report_formats_resource_metadata(self) -> None:
        profile = RuntimeProfile(
            timeline=RuntimeTimeline(stages=()),
            total_ms=1.0,
            resource_statuses=(
                ("Configuration", "READY (Runtime Cache)"),
                ("Prompt Registry", "DEFERRED"),
                ("LLM Manager", "READY (Runtime Cache)"),
            ),
        )
        report = profile.format_report()
        self.assertIn("Runtime Resources", report)
        self.assertIn("READY (Runtime Cache)", report)
        self.assertIn("DEFERRED", report)

    def test_startup_profile_collects_resource_metadata(self) -> None:
        profile = Man1Lab.profile_startup()
        self.assertTrue(profile.resource_statuses)
        statuses = dict(profile.resource_statuses)
        self.assertEqual(statuses["Configuration"], "READY (Runtime Cache)")
        self.assertEqual(statuses["Prompt Registry"], "DEFERRED")
        self.assertIn("LLM Manager", statuses)


class FacadeResourceManagementTest(unittest.TestCase):
    def test_facade_behavior_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            report = platform.list_models()
            self.assertIsNotNone(report)
            self.assertTrue(platform.runtime.context.resource_manager.descriptor(RESOURCE_LLM_MANAGER).initialized)


class RuntimeResourceBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "discovery",
        "agents",
        "providers",
    )

    def test_resources_package_has_no_forbidden_imports(self) -> None:
        resources_dir = REPO_ROOT / "runtime" / "resources"
        offenders: list[str] = []
        for path in sorted(resources_dir.glob("*.py")):
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
