"""Tests for Execution Planning services, ports, and providers."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from discovery.empty import build_empty_discovery
from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution_planning_runtime import StrategyDecisionResult
from models.execution_strategy import ExecutionStrategy, StrategyPosture
from providers.embedded.strategy import EmbeddedStrategyProvider
from providers.noop.strategy import NoOpStrategyProvider
from services.execution_planning.adaptation_service import AdaptationService
from services.execution_planning.generation_service import GenerationService
from services.execution_planning.resource_binding_service import ResourceBindingService
from services.execution_planning.reuse_service import ReuseService
from services.execution_planning.risk_service import RiskService
from services.execution_planning.strategy_service import StrategyService
from tests.fixtures import sample_reproduction_analysis


class ExecutionPlanningServiceInterfaceTest(unittest.TestCase):
    def test_strategy_service_exposes_execute(self) -> None:
        service = StrategyService.default()
        self.assertTrue(callable(getattr(service, "execute", None)))

    def test_resource_binding_service_exposes_execute(self) -> None:
        service = ResourceBindingService.default()
        self.assertTrue(callable(getattr(service, "execute", None)))

    def test_reuse_service_exposes_execute(self) -> None:
        service = ReuseService.default()
        self.assertTrue(callable(getattr(service, "execute", None)))

    def test_adaptation_service_exposes_execute(self) -> None:
        service = AdaptationService.default()
        self.assertTrue(callable(getattr(service, "execute", None)))

    def test_generation_service_exposes_execute(self) -> None:
        service = GenerationService.default()
        self.assertTrue(callable(getattr(service, "execute", None)))

    def test_risk_service_exposes_execute(self) -> None:
        service = RiskService.default()
        self.assertTrue(callable(getattr(service, "execute", None)))


class ExecutionPlanningProviderOrderingTest(unittest.TestCase):
    def test_strategy_service_invokes_providers_in_order(self) -> None:
        first = MagicMock()
        second = MagicMock()
        first.execute.return_value = StrategyDecisionResult(
            strategy=NoOpStrategyProvider().execute(
                sample_reproduction_analysis(),
                build_empty_discovery(sample_reproduction_analysis()),
            ).strategy
        )
        second.execute.return_value = EmbeddedStrategyProvider().execute(
            sample_reproduction_analysis(),
            build_empty_discovery(sample_reproduction_analysis()),
        )
        calls: list[str] = []

        class TrackingFirst:
            def execute(self, analysis, discovery):
                calls.append("first")
                return first.execute(analysis, discovery)

        class TrackingSecond:
            def execute(self, analysis, discovery):
                calls.append("second")
                return second.execute(analysis, discovery)

        service = StrategyService(providers=[TrackingFirst(), TrackingSecond()])
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        result = service.execute(analysis, discovery)

        self.assertEqual(calls, ["first", "second"])
        self.assertIn("rule:greenfield", result.strategy.deciding_factors)


class ExecutionPlanningEmbeddedProviderTest(unittest.TestCase):
    def test_embedded_strategy_provider_returns_rule_based_decision(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        result = EmbeddedStrategyProvider().execute(analysis, discovery)
        self.assertEqual(result.strategy.primary_posture, StrategyPosture.GREENFIELD)
        self.assertIn("rule:greenfield", result.strategy.deciding_factors)

    def test_default_strategy_service_uses_embedded_provider(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        result = StrategyService.default().execute(analysis, discovery)
        self.assertIn("provider:embedded_strategy", result.strategy.deciding_factors)


class ExecutionPlanningNoOpProviderTest(unittest.TestCase):
    def test_noop_strategy_provider_returns_empty_result(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        result = NoOpStrategyProvider().execute(analysis, discovery)
        self.assertEqual(result.strategy.deciding_factors, [])
        self.assertEqual(result.decision_notes, "")

    def test_noop_only_strategy_service_returns_empty_result(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        result = StrategyService(providers=[NoOpStrategyProvider()]).execute(analysis, discovery)
        self.assertEqual(result.strategy.deciding_factors, [])


class ExecutionPlanningRuntimePreservationTest(unittest.TestCase):
    def test_full_service_chain_produces_execution_strategy(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertIsInstance(strategy, ExecutionStrategy)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.GREENFIELD)


class ExecutionPlanningDeterminismTest(unittest.TestCase):
    def test_default_services_are_deterministic(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        first = StrategyService.default().execute(analysis, discovery)
        second = StrategyService.default().execute(analysis, discovery)
        self.assertEqual(first.strategy.model_dump(), second.strategy.model_dump())


class ExecutionPlanningServiceBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = ("workflow", "agents", "hydra", "tracking")

    def test_strategy_service_does_not_import_workflow(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        path = repo_root / "src" / "services" / "execution_planning" / "strategy_service.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders: list[str] = []
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            if module is None:
                continue
            root = module.split(".", 1)[0]
            if root in self._FORBIDDEN_ROOTS:
                offenders.append(module)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
