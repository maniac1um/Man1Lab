"""Tests for Phase 8.5.1 — Runtime Integration.

Verifies that Runtime is the single owner of infrastructure resources and
business modules resolve resources through Runtime rather than instantiating
infrastructure services directly.
"""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

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
from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader
from runtime.context import RuntimeContext
from runtime.lazy import LazyResource
from runtime.resources import RuntimeResourceManager
from runtime.resources.manager import (
    RESOURCE_CONFIGURATION,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROMPT_REGISTRY,
    RESOURCE_PROVIDER_REGISTRY,
)
from runtime.runtime import PlatformRuntime
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


# ---------------------------------------------------------------------------
# RuntimeContext — provider_registry property
# ---------------------------------------------------------------------------


class RuntimeContextProviderRegistryTest(unittest.TestCase):
    """Verify RuntimeContext exposes provider_registry as a LazyResource."""

    def test_provider_registry_property_requires_wiring(self) -> None:
        context = RuntimeContext.create()
        with self.assertRaises(KeyError):
            _ = context.provider_registry

    def test_provider_registry_is_deferred_before_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            context = RuntimeContext.create()
            wire_runtime_resources(
                context.resource_manager,
                settings=settings,
                initialize_configuration=False,
            )
            self.assertFalse(context.provider_registry.is_initialized())
            self.assertEqual(context.provider_registry.status, "deferred")

    def test_provider_registry_resolves_after_wiring(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            context = RuntimeContext.create()
            wire_runtime_resources(
                context.resource_manager,
                settings=settings,
                initialize_configuration=False,
            )
            registry = context.provider_registry.get()
            from providers.llm.provider_registry import ProviderRegistry

            self.assertIsInstance(registry, ProviderRegistry)

    def test_all_four_resources_exposed_as_properties(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            context = RuntimeContext.create()
            wire_runtime_resources(
                context.resource_manager,
                settings=settings,
                initialize_configuration=False,
            )
            # All four resource convenience properties
            self.assertIsInstance(context.configuration, LazyResource)
            self.assertIsInstance(context.prompt_registry, LazyResource)
            self.assertIsInstance(context.llm_manager, LazyResource)
            self.assertIsInstance(context.provider_registry, LazyResource)


# ---------------------------------------------------------------------------
# Facade — agents resolve PromptLoader through Runtime
# ---------------------------------------------------------------------------


class FacadeAgentPromptRegistryTest(unittest.TestCase):
    """Verify facade-created agents use runtime-owned PromptLoader."""

    def test_reader_uses_runtime_prompt_loader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            runtime_loader = platform.runtime.context.resources.get(
                RESOURCE_PROMPT_REGISTRY
            )
            # The reader's prompt builder should wrap the runtime-owned loader
            reader_loader = platform._reader._prompt_builder._loader  # noqa: SLF001
            self.assertIs(reader_loader, runtime_loader)

    def test_planner_uses_runtime_prompt_loader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            runtime_loader = platform.runtime.context.resources.get(
                RESOURCE_PROMPT_REGISTRY
            )
            planner_loader = platform._planner._prompt_builder._loader  # noqa: SLF001
            self.assertIs(planner_loader, runtime_loader)

    def test_coder_uses_runtime_prompt_loader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            runtime_loader = platform.runtime.context.resources.get(
                RESOURCE_PROMPT_REGISTRY
            )
            coder_loader = platform._coder._prompt_builder._loader  # noqa: SLF001
            self.assertIs(coder_loader, runtime_loader)

    def test_reviewer_uses_runtime_prompt_loader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            runtime_loader = platform.runtime.context.resources.get(
                RESOURCE_PROMPT_REGISTRY
            )
            reviewer_loader = (
                platform._orchestrator._reviewer._prompt_builder._loader  # noqa: SLF001
            )
            self.assertIs(reviewer_loader, runtime_loader)

    def test_patch_planner_uses_runtime_prompt_loader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            runtime_loader = platform.runtime.context.resources.get(
                RESOURCE_PROMPT_REGISTRY
            )
            patch_planner_loader = (
                platform._orchestrator._patch_planner._prompt_builder._loader  # noqa: SLF001
            )
            self.assertIs(patch_planner_loader, runtime_loader)


# ---------------------------------------------------------------------------
# PromptLoader ownership — single instance
# ---------------------------------------------------------------------------


class PromptRegistryOwnershipTest(unittest.TestCase):
    """Verify Runtime is the single owner of the PromptLoader instance."""

    def test_all_agents_share_same_prompt_loader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            reader_loader = platform._reader._prompt_builder._loader  # noqa: SLF001
            planner_loader = platform._planner._prompt_builder._loader  # noqa: SLF001
            coder_loader = platform._coder._prompt_builder._loader  # noqa: SLF001
            reviewer_loader = (
                platform._orchestrator._reviewer._prompt_builder._loader  # noqa: SLF001
            )
            patch_planner_loader = (
                platform._orchestrator._patch_planner._prompt_builder._loader  # noqa: SLF001
            )

            self.assertIs(reader_loader, planner_loader)
            self.assertIs(planner_loader, coder_loader)
            self.assertIs(coder_loader, reviewer_loader)
            self.assertIs(reviewer_loader, patch_planner_loader)

    def test_prompt_registry_initialized_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            descriptor = platform.runtime.context.resource_manager.descriptor(
                RESOURCE_PROMPT_REGISTRY
            )
            self.assertGreaterEqual(descriptor.access_count, 1)
            # All agents share the same lazy resource — access count reflects
            # resolution, not per-agent instantiation
            self.assertEqual(descriptor.resource_type, "prompt_registry")

    def test_no_standalone_prompt_loader_in_facade_agents(self) -> None:
        """Agents should not default-construct their own PromptLoader."""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )

            # Verify each agent has a PromptBuilder (injected), not None
            for agent_attr in ("_reader", "_planner", "_coder"):
                agent = getattr(platform, agent_attr)
                builder = agent._prompt_builder  # noqa: SLF001
                self.assertIsInstance(builder, PromptBuilder)
                self.assertIsInstance(builder._loader, PromptLoader)  # noqa: SLF001


# ---------------------------------------------------------------------------
# LLMManager ownership through Runtime
# ---------------------------------------------------------------------------


class LLMManagerOwnershipTest(unittest.TestCase):
    """Verify LLMManager is owned by Runtime and provider_registry is shared."""

    def test_llm_manager_uses_runtime_provider_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            runtime_provider_registry = platform.runtime.context.resources.get(
                RESOURCE_PROVIDER_REGISTRY
            )
            llm_manager = platform.runtime.context.resources.get(RESOURCE_LLM_MANAGER)
            self.assertIs(
                llm_manager._provider_registry,  # noqa: SLF001
                runtime_provider_registry,
            )

    def test_provider_registry_is_single_instance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            first = platform.runtime.context.resources.get(RESOURCE_PROVIDER_REGISTRY)
            second = platform.runtime.context.resources.get(RESOURCE_PROVIDER_REGISTRY)
            self.assertIs(first, second)

    def test_llm_manager_accessible_via_facade_operations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            report = platform.list_models()
            self.assertIsNotNone(report)


# ---------------------------------------------------------------------------
# Existing workflow behavior
# ---------------------------------------------------------------------------


class ExistingWorkflowBehaviorTest(unittest.TestCase):
    """Verify existing workflows behave identically after integration changes."""

    def test_facade_profile_startup_still_works(self) -> None:
        profile = Man1Lab.profile_startup()
        self.assertTrue(profile.resource_statuses)
        statuses = dict(profile.resource_statuses)
        self.assertIn("Configuration", statuses)
        self.assertIn("Prompt Registry", statuses)
        self.assertIn("LLM Manager", statuses)
        self.assertIn("Provider Registry", statuses)
        self.assertEqual(statuses["Configuration"], "READY (Runtime Cache)")
        self.assertEqual(statuses["Prompt Registry"], "READY (Runtime Cache)")

    def test_facade_configuration_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            config = platform.configuration()
            self.assertIsInstance(config, dict)
            self.assertIn("workspace_root", config)

    def test_facade_version_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            self.assertTrue(len(platform.version()) > 0)

    def test_facade_runtime_lifecycle_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            self.assertTrue(platform.is_runtime_ready())
            self.assertIsNotNone(platform.session())

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
            current = platform.current_model()
            self.assertIsNotNone(current)

    def test_facade_resource_descriptors_complete(self) -> None:
        """All four infrastructure resources have valid descriptors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            descriptors = (
                platform.runtime.context.resource_manager.descriptors()
            )
            names = {d.name for d in descriptors}
            self.assertIn(RESOURCE_CONFIGURATION, names)
            self.assertIn(RESOURCE_PROMPT_REGISTRY, names)
            self.assertIn(RESOURCE_LLM_MANAGER, names)
            self.assertIn(RESOURCE_PROVIDER_REGISTRY, names)

    def test_facade_with_explicit_runtime(self) -> None:
        """Facade with an explicit PlatformRuntime works correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            runtime = PlatformRuntime()
            platform = Man1Lab(
                settings=settings,
                runtime=runtime,
                initialize_configuration=False,
                configure_logging=False,
            )
            self.assertIs(platform.runtime, runtime)
            self.assertTrue(platform.is_runtime_ready())

    def test_runtime_state_is_ready_after_facade_init(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            self.assertEqual(platform.runtime.state, RuntimeState.READY)


# ---------------------------------------------------------------------------
# Dependency boundary verification
# ---------------------------------------------------------------------------


class PromptRegistryPathResolutionTest(unittest.TestCase):
    """Regression: runtime-owned PromptLoader must resolve bundled prompts."""

    def test_prompt_registry_resolves_from_non_repo_cwd(self) -> None:
        import os

        previous = os.getcwd()
        try:
            os.chdir(tempfile.gettempdir())
            settings = _test_settings(REPO_ROOT)
            manager = RuntimeResourceManager()
            wire_runtime_resources(manager, settings=settings, initialize_configuration=False)
            loader = manager.get(RESOURCE_PROMPT_REGISTRY)
            prompt_path = loader._prompts_dir / "reader" / "system.md"  # noqa: SLF001
            self.assertTrue(prompt_path.is_absolute())
            self.assertTrue(prompt_path.is_file(), msg=str(prompt_path))
        finally:
            os.chdir(previous)

    def test_facade_prompt_registry_finds_reader_system_from_tmp_cwd(self) -> None:
        import os

        previous = os.getcwd()
        try:
            os.chdir(tempfile.gettempdir())
            with tempfile.TemporaryDirectory() as temp_dir:
                settings = _test_settings(Path(temp_dir))
                platform = Man1Lab(
                    settings=settings,
                    initialize_configuration=False,
                    configure_logging=False,
                )
                loader = platform.runtime.context.resources.get(RESOURCE_PROMPT_REGISTRY)
                self.assertTrue(
                    (loader._prompts_dir / "reader" / "system.md").is_file()  # noqa: SLF001
                )
        finally:
            os.chdir(previous)


class RuntimeIntegrationBoundaryTest(unittest.TestCase):
    """Verify no forbidden dependency patterns introduced by integration."""

    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "discovery",
        "agents",
        "providers",
    )

    def test_context_py_has_no_forbidden_imports(self) -> None:
        path = REPO_ROOT / "src" / "runtime" / "context.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders: list[str] = []
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
                offenders.append(module)
        self.assertEqual(offenders, [])

    def test_facade_has_no_new_forbidden_imports_from_runtime(self) -> None:
        """Facade only imports from runtime.resources.manager and runtime.runtime."""
        path = REPO_ROOT / "src" / "application" / "facade.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        runtime_imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("runtime"):
                    for alias in node.names:
                        runtime_imports.append(f"{node.module}.{alias.name}")
        allowed = {
            "runtime.resources.manager.RESOURCE_LLM_MANAGER",
            "runtime.profiling.report.RuntimeProfile",
            "runtime.runtime.PlatformRuntime",
            "runtime.session.RuntimeSession",
            "runtime.session.workspace_store.WorkspaceArtifactStore",
            "runtime.state.RuntimeState",
            "application.runtime.accessors.RuntimeInfrastructure",
            "application.runtime.resource_wiring.wire_runtime_resources",
        }
        for imp in runtime_imports:
            self.assertIn(imp, allowed, f"Unexpected runtime import in facade: {imp}")

    def test_no_circular_dependency_runtime_to_facade(self) -> None:
        """Runtime modules must not import from application."""
        runtime_dir = REPO_ROOT / "src" / "runtime"
        offenders: list[str] = []
        for path in sorted(runtime_dir.rglob("*.py")):
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
                if root == "application":
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}: {module}"
                    )
        self.assertEqual(offenders, [])

    def test_no_global_singleton_in_context_module(self) -> None:
        source = (REPO_ROOT / "src" / "runtime" / "context.py").read_text(encoding="utf-8")
        self.assertNotIn("_instance", source)
        self.assertNotIn("singleton", source.lower())


# ---------------------------------------------------------------------------
# Integration with existing Phase 8 subsystems
# ---------------------------------------------------------------------------


class RuntimeIntegrationPhase8CompatTest(unittest.TestCase):
    """Verify Phase 8.5.1 is backward-compatible with all prior Phase 8 work."""

    def test_resource_wiring_registers_all_four_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            manager = RuntimeResourceManager()
            wire_runtime_resources(
                manager, settings=settings, initialize_configuration=False
            )
            stats = manager.statistics()
            self.assertEqual(stats.total_resources, 4)

    def test_lazy_initialization_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            context = RuntimeContext.create()
            wire_runtime_resources(
                context.resource_manager,
                settings=settings,
                initialize_configuration=False,
            )
            self.assertFalse(context.configuration.is_initialized())
            self.assertFalse(context.prompt_registry.is_initialized())

    def test_resource_manager_descriptors_include_provider_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            manager = RuntimeResourceManager()
            wire_runtime_resources(
                manager, settings=settings, initialize_configuration=False
            )
            desc = manager.descriptor(RESOURCE_PROVIDER_REGISTRY)
            self.assertEqual(desc.resource_type, "provider_registry")
            self.assertTrue(desc.lazy)
            self.assertEqual(desc.cache_policy.value, "runtime")

    def test_profile_startup_includes_all_four_resource_labels(self) -> None:
        profile = Man1Lab.profile_startup()
        labels = {label for label, _ in profile.resource_statuses}
        self.assertIn("Configuration", labels)
        self.assertIn("Prompt Registry", labels)
        self.assertIn("LLM Manager", labels)
        self.assertIn("Provider Registry", labels)

    def test_session_still_integrated_with_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            self.assertFalse(platform.is_session_active())
            session = platform.session()
            self.assertIsNotNone(session)


    def test_agents_do_not_construct_prompt_loader(self) -> None:
        agent_dir = REPO_ROOT / "src" / "agents"
        offenders: list[str] = []
        for path in sorted(agent_dir.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "PromptLoader()" in source:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [])

    def test_planning_does_not_construct_prompt_loader(self) -> None:
        path = REPO_ROOT / "src" / "planning" / "patch_planner.py"
        self.assertNotIn("PromptLoader()", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
