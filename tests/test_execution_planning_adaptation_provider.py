"""Tests for Embedded Adaptation Provider and Decision Foundation adaptation — Phase 6.4."""

from __future__ import annotations

import unittest
from pathlib import Path

from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution_strategy import AdaptationScope, ModificationClass, ReuseMode, StrategyPosture
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from providers.embedded.adaptation import EmbeddedAdaptationProvider
from providers.embedded.decision_foundation import build_observed_facts, decide_adaptation, evaluate_dimensions
from providers.embedded.resource_binding import EmbeddedResourceBindingProvider
from providers.embedded.reuse import EmbeddedReuseProvider
from providers.embedded.strategy import EmbeddedStrategyProvider
from services.execution_planning.adaptation_service import AdaptationService
from tests.fixtures import sample_reproduction_analysis
from tests.test_execution_planning_binding_provider import _discovery_full_bindings
from tests.test_execution_planning_strategy_provider import _discovery_greenfield, _discovery_hybrid, _discovery_reuse


def _reuse_result_for(analysis: PaperReproductionAnalysis, discovery: ResearchResourceDiscovery):
    strategy = EmbeddedStrategyProvider().execute(analysis, discovery)
    binding = EmbeddedResourceBindingProvider().execute(analysis, discovery, strategy)
    return EmbeddedReuseProvider().execute(analysis, discovery, binding)


class DecisionFoundationAdaptationTest(unittest.TestCase):
    def test_decide_adaptation_uses_shared_facts_and_dimensions(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        reuse_result = _reuse_result_for(analysis, discovery)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_adaptation(
            facts,
            dimensions,
            reuse_result.strategy,
            reuse_result.resource_bindings,
            reuse_result.reuse_plan,
        )
        self.assertTrue(decision.adaptation_required)
        self.assertIn("dimension:adaptation_requirement", decision.provider_factors[4])


class EmbeddedAdaptationProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        self.provider = EmbeddedAdaptationProvider()

    def _execute(self, discovery: ResearchResourceDiscovery):
        reuse_result = _reuse_result_for(self.analysis, discovery)
        return self.provider.execute(self.analysis, discovery, reuse_result), reuse_result

    def test_as_is_produces_no_modifications(self) -> None:
        result, reuse_result = self._execute(_discovery_reuse(self.analysis))
        self.assertEqual(reuse_result.reuse_plan.reuse_mode, ReuseMode.AS_IS)
        self.assertFalse(result.adaptation_plan.adaptation_required)
        self.assertEqual(result.adaptation_plan.adaptation_scope, AdaptationScope.NONE)
        self.assertEqual(result.adaptation_plan.authorized_modifications, [])

    def test_hybrid_components_produces_authorized_modifications(self) -> None:
        result, reuse_result = self._execute(_discovery_hybrid(self.analysis))
        self.assertEqual(reuse_result.reuse_plan.reuse_mode, ReuseMode.HYBRID_COMPONENTS)
        self.assertTrue(result.adaptation_plan.adaptation_required)
        self.assertGreater(len(result.adaptation_plan.authorized_modifications), 0)
        classes = {mod.modification_class for mod in result.adaptation_plan.authorized_modifications}
        self.assertIn(ModificationClass.CONFIG_PATCH, classes)

    def test_greenfield_posture_produces_empty_adaptation(self) -> None:
        result, _ = self._execute(_discovery_greenfield(self.analysis))
        self.assertFalse(result.adaptation_plan.adaptation_required)
        self.assertEqual(result.adaptation_plan.authorized_modifications, [])

    def test_supporting_resources_produce_limited_adaptation(self) -> None:
        result, reuse_result = self._execute(_discovery_full_bindings(self.analysis))
        self.assertEqual(reuse_result.reuse_plan.reuse_mode, ReuseMode.AS_IS)
        self.assertTrue(result.adaptation_plan.adaptation_required)
        self.assertEqual(result.adaptation_plan.adaptation_scope, AdaptationScope.MINIMAL)
        supporting_mods = [
            mod
            for mod in result.adaptation_plan.authorized_modifications
            if mod.target_binding_id
            and any(
                binding.binding_id == mod.target_binding_id
                and binding.role.value in {"fallback_repository", "supporting_asset"}
                for binding in reuse_result.resource_bindings.bindings
            )
        ]
        self.assertGreater(len(supporting_mods), 0)

    def test_authorized_modification_generation(self) -> None:
        result, _ = self._execute(_discovery_hybrid(self.analysis))
        for modification in result.adaptation_plan.authorized_modifications:
            self.assertIn(
                modification.modification_class,
                {
                    ModificationClass.CONFIG_PATCH,
                    ModificationClass.SCRIPT_PATCH,
                    ModificationClass.DEPENDENCY_PIN,
                },
            )
            self.assertNotIn(
                modification.modification_class,
                {ModificationClass.FORK, ModificationClass.FRAMEWORK_PORT},
            )

    def test_deterministic_execution(self) -> None:
        discovery = _discovery_hybrid(self.analysis)
        reuse_result = _reuse_result_for(self.analysis, discovery)
        first = self.provider.execute(self.analysis, discovery, reuse_result)
        second = self.provider.execute(self.analysis, discovery, reuse_result)
        self.assertEqual(first.adaptation_plan.model_dump(), second.adaptation_plan.model_dump())
        self.assertEqual(first.decision_notes, second.decision_notes)

    def test_rationale_generation(self) -> None:
        result, _ = self._execute(_discovery_hybrid(self.analysis))
        self.assertIn("Hybrid reuse requires authorized engineering adaptation", result.decision_notes)

    def test_decision_notes(self) -> None:
        result, _ = self._execute(_discovery_hybrid(self.analysis))
        self.assertIn("Evaluating reusable components", result.decision_notes)
        self.assertIn("adaptation_scope", result.diagnostics)

    def test_immutable_inputs(self) -> None:
        discovery = _discovery_hybrid(self.analysis)
        reuse_result = _reuse_result_for(self.analysis, discovery)
        analysis_before = self.analysis.model_dump(mode="json")
        discovery_before = discovery.model_dump(mode="json")
        reuse_before = reuse_result.model_dump(mode="json")
        self.provider.execute(self.analysis, discovery, reuse_result)
        self.assertEqual(self.analysis.model_dump(mode="json"), analysis_before)
        self.assertEqual(discovery.model_dump(mode="json"), discovery_before)
        self.assertEqual(reuse_result.model_dump(mode="json"), reuse_before)


class EmbeddedAdaptationIntegrationTest(unittest.TestCase):
    def test_service_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        reuse_result = _reuse_result_for(analysis, discovery)
        result = AdaptationService.default().execute(analysis, discovery, reuse_result)
        self.assertTrue(result.adaptation_plan.adaptation_required)

    def test_workflow_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.HYBRID)
        self.assertTrue(strategy.adaptation_plan.adaptation_required)


class EmbeddedAdaptationProviderParityTest(unittest.TestCase):
    def test_provider_matches_decide_adaptation(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        reuse_result = _reuse_result_for(analysis, discovery)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_adaptation(
            facts,
            dimensions,
            reuse_result.strategy,
            reuse_result.resource_bindings,
            reuse_result.reuse_plan,
        )
        provider = EmbeddedAdaptationProvider().execute(analysis, discovery, reuse_result)
        self.assertEqual(decision.adaptation_required, provider.adaptation_plan.adaptation_required)
        self.assertEqual(decision.adaptation_scope, provider.adaptation_plan.adaptation_scope)
        self.assertEqual(
            [mod.model_dump() for mod in decision.authorized_modifications],
            [mod.model_dump() for mod in provider.adaptation_plan.authorized_modifications],
        )


if __name__ == "__main__":
    unittest.main()
