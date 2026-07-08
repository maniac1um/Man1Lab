"""Tests for Embedded Reuse Provider and Decision Foundation reuse — Phase 6.3."""

from __future__ import annotations

import unittest
from pathlib import Path

from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution_strategy import BindingRole, ReuseMode
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from providers.embedded.decision_foundation import build_observed_facts, decide_reuse, evaluate_dimensions
from providers.embedded.resource_binding import EmbeddedResourceBindingProvider
from providers.embedded.reuse import EmbeddedReuseProvider
from providers.embedded.strategy import EmbeddedStrategyProvider
from services.execution_planning.reuse_service import ReuseService
from tests.fixtures import sample_reproduction_analysis
from tests.test_execution_planning_binding_provider import (
    _discovery_full_bindings,
    _discovery_unverified_repo,
)
from tests.test_execution_planning_strategy_provider import (
    _discovery_greenfield,
    _discovery_reuse,
)


def _binding_result_for(analysis: PaperReproductionAnalysis, discovery: ResearchResourceDiscovery):
    strategy = EmbeddedStrategyProvider().execute(analysis, discovery)
    return EmbeddedResourceBindingProvider().execute(analysis, discovery, strategy)


class DecisionFoundationReuseTest(unittest.TestCase):
    def test_decide_reuse_uses_shared_facts_and_dimensions(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_full_bindings(analysis)
        binding_result = _binding_result_for(analysis, discovery)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_reuse(
            facts,
            dimensions,
            binding_result.resource_bindings,
            binding_result.strategy,
        )
        self.assertGreater(len(decision.components_to_reuse), 0)
        self.assertIn("dimension:reuse_opportunity", decision.provider_factors[3])


class EmbeddedReuseProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        self.provider = EmbeddedReuseProvider()

    def _execute(self, discovery: ResearchResourceDiscovery):
        binding_result = _binding_result_for(self.analysis, discovery)
        return self.provider.execute(self.analysis, discovery, binding_result), binding_result

    def test_repository_reuse(self) -> None:
        result, binding_result = self._execute(_discovery_reuse(self.analysis))
        repo_bindings = [
            component
            for component in result.reuse_plan.components_to_reuse
            if any(
                binding.binding_id == component.binding_id
                and binding.role == BindingRole.PRIMARY_REPOSITORY
                for binding in binding_result.resource_bindings.bindings
            )
        ]
        self.assertEqual(len(repo_bindings), 1)
        self.assertEqual(repo_bindings[0].component_label, "repository")

    def test_checkpoint_reuse(self) -> None:
        result, _ = self._execute(_discovery_full_bindings(self.analysis))
        labels = {component.component_label for component in result.reuse_plan.components_to_reuse}
        self.assertIn("checkpoint", labels)

    def test_dataset_reuse(self) -> None:
        result, _ = self._execute(_discovery_full_bindings(self.analysis))
        labels = {component.component_label for component in result.reuse_plan.components_to_reuse}
        self.assertIn("dataset", labels)

    def test_supporting_resource_reuse(self) -> None:
        result, _ = self._execute(_discovery_full_bindings(self.analysis))
        labels = {component.component_label for component in result.reuse_plan.components_to_reuse}
        self.assertIn("fallback_repository", labels)

    def test_excluded_component_generation(self) -> None:
        discovery = _discovery_unverified_repo(self.analysis)
        result, _ = self._execute(discovery)
        self.assertGreater(len(result.reuse_plan.components_excluded), 0)
        self.assertEqual(result.reuse_plan.components_to_reuse, [])

    def test_no_reusable_resources(self) -> None:
        discovery = _discovery_greenfield(self.analysis)
        result, _ = self._execute(discovery)
        self.assertEqual(result.reuse_plan.reuse_mode, ReuseMode.NOT_APPLICABLE)
        self.assertEqual(result.reuse_plan.components_to_reuse, [])

    def test_deterministic_execution(self) -> None:
        discovery = _discovery_full_bindings(self.analysis)
        binding_result = _binding_result_for(self.analysis, discovery)
        first = self.provider.execute(self.analysis, discovery, binding_result)
        second = self.provider.execute(self.analysis, discovery, binding_result)
        self.assertEqual(first.reuse_plan.model_dump(), second.reuse_plan.model_dump())
        self.assertEqual(first.decision_notes, second.decision_notes)

    def test_rationale_generation(self) -> None:
        result, _ = self._execute(_discovery_reuse(self.analysis))
        self.assertTrue(result.reuse_plan.reuse_assumptions)
        self.assertIn("Reuse opportunity dimension", result.reuse_plan.reuse_assumptions[1])

    def test_decision_notes(self) -> None:
        result, _ = self._execute(_discovery_full_bindings(self.analysis))
        self.assertIn("Evaluating bound resources", result.decision_notes)
        self.assertIn("reuse_mode", result.diagnostics)

    def test_immutable_inputs(self) -> None:
        discovery = _discovery_full_bindings(self.analysis)
        binding_result = _binding_result_for(self.analysis, discovery)
        analysis_before = self.analysis.model_dump(mode="json")
        discovery_before = discovery.model_dump(mode="json")
        binding_before = binding_result.model_dump(mode="json")
        self.provider.execute(self.analysis, discovery, binding_result)
        self.assertEqual(self.analysis.model_dump(mode="json"), analysis_before)
        self.assertEqual(discovery.model_dump(mode="json"), discovery_before)
        self.assertEqual(binding_result.model_dump(mode="json"), binding_before)


class EmbeddedReuseIntegrationTest(unittest.TestCase):
    def test_service_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_full_bindings(analysis)
        binding_result = _binding_result_for(analysis, discovery)
        result = ReuseService.default().execute(analysis, discovery, binding_result)
        self.assertGreater(len(result.reuse_plan.components_to_reuse), 0)
        self.assertEqual(result.reuse_plan.reuse_mode, ReuseMode.AS_IS)

    def test_workflow_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_full_bindings(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertGreater(len(strategy.reuse_plan.components_to_reuse), 0)
        self.assertIsNotNone(strategy.reuse_plan.primary_reuse_binding_id)


class EmbeddedReuseProviderParityTest(unittest.TestCase):
    def test_provider_matches_decide_reuse(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_full_bindings(analysis)
        binding_result = _binding_result_for(analysis, discovery)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_reuse(
            facts,
            dimensions,
            binding_result.resource_bindings,
            binding_result.strategy,
        )
        provider = EmbeddedReuseProvider().execute(analysis, discovery, binding_result)
        self.assertEqual(decision.reuse_mode, provider.reuse_plan.reuse_mode)
        self.assertEqual(
            [component.model_dump() for component in decision.components_to_reuse],
            [component.model_dump() for component in provider.reuse_plan.components_to_reuse],
        )


if __name__ == "__main__":
    unittest.main()
