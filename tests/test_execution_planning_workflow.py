"""Tests for Execution PlanningWorkflow skeleton coordinator."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from execution_planning.builder import ExecutionStrategyBuilder
from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution_planning_runtime import (
    AdaptationPlanResult,
    AdaptationPlanSnapshot,
    GenerationPlanResult,
    GenerationPlanSnapshot,
    ResourceBindingResult,
    ResourceBindingSnapshot,
    ReusePlanResult,
    ReusePlanSnapshot,
    RiskAssessmentResult,
    RiskAssessmentSnapshot,
    StrategyDecisionResult,
    StrategyDecisionSnapshot,
)
from models.execution_strategy import ExecutionStrategy, PlanningStatus, StrategyPosture
from discovery.empty import build_empty_discovery
from tests.fixtures import sample_reproduction_analysis


def _strategy_result() -> StrategyDecisionResult:
    return StrategyDecisionResult(
        strategy=StrategyDecisionSnapshot(
            primary_posture=StrategyPosture.GREENFIELD,
            rationale="mock",
            artifact_status_hint=PlanningStatus.PARTIAL,
        )
    )


def _binding_result(strategy: StrategyDecisionResult) -> ResourceBindingResult:
    return ResourceBindingResult(
        strategy=strategy.strategy,
        resource_bindings=ResourceBindingSnapshot(),
    )


def _reuse_result(binding: ResourceBindingResult) -> ReusePlanResult:
    return ReusePlanResult(
        strategy=binding.strategy,
        resource_bindings=binding.resource_bindings,
        reuse_plan=ReusePlanSnapshot(),
    )


def _adaptation_result(reuse: ReusePlanResult) -> AdaptationPlanResult:
    return AdaptationPlanResult(
        strategy=reuse.strategy,
        resource_bindings=reuse.resource_bindings,
        reuse_plan=reuse.reuse_plan,
        adaptation_plan=AdaptationPlanSnapshot(),
    )


def _generation_result(adaptation: AdaptationPlanResult) -> GenerationPlanResult:
    return GenerationPlanResult(
        strategy=adaptation.strategy,
        resource_bindings=adaptation.resource_bindings,
        reuse_plan=adaptation.reuse_plan,
        adaptation_plan=adaptation.adaptation_plan,
        generation_plan=GenerationPlanSnapshot(),
    )


def _risk_result(generation: GenerationPlanResult) -> RiskAssessmentResult:
    return RiskAssessmentResult(
        strategy=generation.strategy,
        resource_bindings=generation.resource_bindings,
        reuse_plan=generation.reuse_plan,
        adaptation_plan=generation.adaptation_plan,
        generation_plan=generation.generation_plan,
        risk_assessment=RiskAssessmentSnapshot(artifact_status_hint=PlanningStatus.PARTIAL),
    )


class ExecutionPlanningWorkflowConstructionTest(unittest.TestCase):
    def test_workflow_accepts_injected_dependencies(self) -> None:
        workflow = ExecutionPlanningWorkflow(
            strategy_service=MagicMock(),
            resource_binding_service=MagicMock(),
            reuse_service=MagicMock(),
            adaptation_service=MagicMock(),
            generation_service=MagicMock(),
            risk_service=MagicMock(),
            builder=ExecutionStrategyBuilder,
        )
        self.assertIsInstance(workflow, ExecutionPlanningWorkflow)

    def test_default_factory_returns_workflow(self) -> None:
        workflow = ExecutionPlanningWorkflow.default()
        self.assertIsInstance(workflow, ExecutionPlanningWorkflow)


class ExecutionPlanningWorkflowOrchestrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        self.discovery = build_empty_discovery(self.analysis)

        self.strategy_service = MagicMock()
        self.binding_service = MagicMock()
        self.reuse_service = MagicMock()
        self.adaptation_service = MagicMock()
        self.generation_service = MagicMock()
        self.risk_service = MagicMock()
        self.builder = MagicMock()
        self.builder.build.return_value = MagicMock(spec=ExecutionStrategy)

        strategy_result = _strategy_result()
        binding_result = _binding_result(strategy_result)
        reuse_result = _reuse_result(binding_result)
        adaptation_result = _adaptation_result(reuse_result)
        generation_result = _generation_result(adaptation_result)
        risk_result = _risk_result(generation_result)

        self.strategy_service.execute.return_value = strategy_result
        self.binding_service.execute.return_value = binding_result
        self.reuse_service.execute.return_value = reuse_result
        self.adaptation_service.execute.return_value = adaptation_result
        self.generation_service.execute.return_value = generation_result
        self.risk_service.execute.return_value = risk_result

        self.workflow = ExecutionPlanningWorkflow(
            strategy_service=self.strategy_service,
            resource_binding_service=self.binding_service,
            reuse_service=self.reuse_service,
            adaptation_service=self.adaptation_service,
            generation_service=self.generation_service,
            risk_service=self.risk_service,
            builder=self.builder,
        )

    def test_stage_ordering(self) -> None:
        self.workflow.run(self.analysis, self.discovery)

        self.strategy_service.execute.assert_called_once_with(self.analysis, self.discovery)
        self.binding_service.execute.assert_called_once_with(
            self.analysis,
            self.discovery,
            self.strategy_service.execute.return_value,
        )
        self.reuse_service.execute.assert_called_once_with(
            self.analysis,
            self.discovery,
            self.binding_service.execute.return_value,
        )
        self.adaptation_service.execute.assert_called_once_with(
            self.analysis,
            self.discovery,
            self.reuse_service.execute.return_value,
        )
        self.generation_service.execute.assert_called_once_with(
            self.analysis,
            self.discovery,
            self.adaptation_service.execute.return_value,
        )
        self.risk_service.execute.assert_called_once_with(
            self.analysis,
            self.discovery,
            self.generation_service.execute.return_value,
        )

    def test_builder_invocation(self) -> None:
        self.workflow.run(self.analysis, self.discovery)
        self.builder.build.assert_called_once()
        risk_arg = self.builder.build.call_args.args[0]
        self.assertIsInstance(risk_arg, RiskAssessmentResult)

    def test_returns_execution_strategy(self) -> None:
        expected = MagicMock(spec=ExecutionStrategy)
        self.builder.build.return_value = expected
        result = self.workflow.run(self.analysis, self.discovery)
        self.assertIs(result, expected)

    def test_runtime_results_never_exposed(self) -> None:
        result = self.workflow.run(self.analysis, self.discovery)
        self.assertIsInstance(result, ExecutionStrategy)
        self.assertNotIsInstance(result, RiskAssessmentResult)


class ExecutionPlanningWorkflowInputOwnershipTest(unittest.TestCase):
    def test_analysis_and_discovery_remain_immutable(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        analysis_before = analysis.model_dump(mode="json")
        discovery_before = discovery.model_dump(mode="json")

        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)

        self.assertEqual(analysis.model_dump(mode="json"), analysis_before)
        self.assertEqual(discovery.model_dump(mode="json"), discovery_before)
        self.assertIsInstance(strategy, ExecutionStrategy)


class ExecutionPlanningWorkflowDeterminismTest(unittest.TestCase):
    def test_default_skeleton_execution_is_deterministic_in_structure(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        workflow = ExecutionPlanningWorkflow.default()

        first = workflow.run(analysis, discovery)
        second = workflow.run(analysis, discovery)

        self.assertEqual(first.strategy.primary_posture, second.strategy.primary_posture)
        self.assertEqual(first.strategy.primary_posture, StrategyPosture.GREENFIELD)
        self.assertEqual(first.metadata.status, second.metadata.status)


class ExecutionPlanningWorkflowSimplificationTest(unittest.TestCase):
    def test_workflow_contains_no_placeholder_stages(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = (repo_root / "execution_planning" / "workflow.py").read_text(encoding="utf-8")
        self.assertNotIn("_run_strategy_stage", source)
        self.assertNotIn("_PlaceholderStrategyService", source)
        self.assertNotIn(".plan(", source)


class ExecutionPlanningWorkflowBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "providers",
        "agents",
        "workflow",
        "hydra",
        "tracking",
        "llm",
    )

    def test_workflow_imports_only_services_not_providers(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        workflow_path = repo_root / "execution_planning" / "workflow.py"
        tree = ast.parse(workflow_path.read_text(encoding="utf-8"))
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

    def test_workflow_imports_services(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = (repo_root / "execution_planning" / "workflow.py").read_text(encoding="utf-8")
        self.assertIn("services.execution_planning", source)


if __name__ == "__main__":
    unittest.main()
