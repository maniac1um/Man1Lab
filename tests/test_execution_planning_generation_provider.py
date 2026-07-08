"""Tests for Embedded Generation Provider and Decision Foundation generation — Phase 6.5."""

from __future__ import annotations

import unittest
from pathlib import Path

from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution_strategy import (
    AnalysisModule,
    GenerationIntent,
    GenerationScope,
    ReuseMode,
    StrategyPosture,
)
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from providers.embedded.adaptation import EmbeddedAdaptationProvider
from providers.embedded.decision_foundation import build_observed_facts, decide_generation, evaluate_dimensions
from providers.embedded.generation import EmbeddedGenerationProvider
from providers.embedded.resource_binding import EmbeddedResourceBindingProvider
from providers.embedded.reuse import EmbeddedReuseProvider
from providers.embedded.strategy import EmbeddedStrategyProvider
from services.execution_planning.generation_service import GenerationService
from tests.fixtures import sample_reproduction_analysis
from tests.test_execution_planning_binding_provider import _discovery_full_bindings
from tests.test_execution_planning_strategy_provider import _discovery_greenfield, _discovery_hybrid, _discovery_reuse


def _reuse_result_for(analysis: PaperReproductionAnalysis, discovery: ResearchResourceDiscovery):
    strategy = EmbeddedStrategyProvider().execute(analysis, discovery)
    binding = EmbeddedResourceBindingProvider().execute(analysis, discovery, strategy)
    return EmbeddedReuseProvider().execute(analysis, discovery, binding)


def _adaptation_result_for(analysis: PaperReproductionAnalysis, discovery: ResearchResourceDiscovery):
    reuse_result = _reuse_result_for(analysis, discovery)
    return EmbeddedAdaptationProvider().execute(analysis, discovery, reuse_result)


class DecisionFoundationGenerationTest(unittest.TestCase):
    def test_decide_generation_uses_shared_facts_and_dimensions(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_greenfield(analysis)
        adaptation_result = _adaptation_result_for(analysis, discovery)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_generation(
            facts,
            dimensions,
            adaptation_result.strategy,
            adaptation_result.resource_bindings,
            adaptation_result.reuse_plan,
            adaptation_result.adaptation_plan,
        )
        self.assertTrue(decision.generation_required)
        self.assertIn("dimension:generation_requirement", decision.provider_factors[3])


class EmbeddedGenerationProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        self.provider = EmbeddedGenerationProvider()

    def _execute(self, discovery: ResearchResourceDiscovery):
        adaptation_result = _adaptation_result_for(self.analysis, discovery)
        return self.provider.execute(self.analysis, discovery, adaptation_result), adaptation_result

    def test_greenfield_generates_engineering_artifacts(self) -> None:
        result, adaptation_result = self._execute(_discovery_greenfield(self.analysis))
        self.assertEqual(adaptation_result.strategy.primary_posture, StrategyPosture.GREENFIELD)
        self.assertTrue(result.generation_plan.generation_required)
        self.assertEqual(result.generation_plan.generation_scope, GenerationScope.FULL_CODEBASE)
        self.assertGreaterEqual(len(result.generation_plan.modules_to_generate), 4)
        modules = {target.analysis_module for target in result.generation_plan.modules_to_generate}
        self.assertIn(AnalysisModule.RESOURCES, modules)
        self.assertIn(AnalysisModule.EVALUATION, modules)

    def test_official_repository_as_is_generates_nothing(self) -> None:
        result, adaptation_result = self._execute(_discovery_reuse(self.analysis))
        self.assertEqual(adaptation_result.reuse_plan.reuse_mode, ReuseMode.AS_IS)
        self.assertFalse(result.generation_plan.generation_required)
        self.assertEqual(result.generation_plan.generation_scope, GenerationScope.NONE)
        self.assertEqual(result.generation_plan.modules_to_generate, [])

    def test_hybrid_generates_missing_artifacts(self) -> None:
        result, adaptation_result = self._execute(_discovery_hybrid(self.analysis))
        self.assertEqual(adaptation_result.reuse_plan.reuse_mode, ReuseMode.HYBRID_COMPONENTS)
        self.assertTrue(result.generation_plan.generation_required)
        self.assertEqual(result.generation_plan.generation_scope, GenerationScope.MISSING_MODULES)
        self.assertGreater(len(result.generation_plan.modules_to_generate), 0)

    def test_supporting_resources_generate_integration_artifacts(self) -> None:
        result, adaptation_result = self._execute(_discovery_full_bindings(self.analysis))
        self.assertTrue(adaptation_result.adaptation_plan.adaptation_required)
        intents = {target.generation_intent for target in result.generation_plan.modules_to_generate}
        self.assertIn(GenerationIntent.STUB_FOR_INTEGRATION, intents)

    def test_generation_target_creation(self) -> None:
        result, _ = self._execute(_discovery_hybrid(self.analysis))
        for target in result.generation_plan.modules_to_generate:
            self.assertIn(
                target.generation_intent,
                {
                    GenerationIntent.STUB_FOR_INTEGRATION,
                    GenerationIntent.REPLACE_MISSING_UPSTREAM,
                },
            )
            self.assertNotEqual(target.generation_intent, GenerationIntent.IMPLEMENT_FROM_PAPER)

    def test_deterministic_execution(self) -> None:
        discovery = _discovery_hybrid(self.analysis)
        adaptation_result = _adaptation_result_for(self.analysis, discovery)
        first = self.provider.execute(self.analysis, discovery, adaptation_result)
        second = self.provider.execute(self.analysis, discovery, adaptation_result)
        self.assertEqual(first.generation_plan.model_dump(), second.generation_plan.model_dump())
        self.assertEqual(first.decision_notes, second.decision_notes)

    def test_rationale_generation(self) -> None:
        result, _ = self._execute(_discovery_greenfield(self.analysis))
        self.assertIn("Greenfield posture requires generation", result.generation_plan.generation_rationale)

    def test_decision_notes(self) -> None:
        result, _ = self._execute(_discovery_hybrid(self.analysis))
        self.assertIn("generation_scope", result.diagnostics)
        self.assertIn("Generation scope", result.decision_notes)

    def test_immutable_inputs(self) -> None:
        discovery = _discovery_hybrid(self.analysis)
        adaptation_result = _adaptation_result_for(self.analysis, discovery)
        analysis_before = self.analysis.model_dump(mode="json")
        discovery_before = discovery.model_dump(mode="json")
        adaptation_before = adaptation_result.model_dump(mode="json")
        self.provider.execute(self.analysis, discovery, adaptation_result)
        self.assertEqual(self.analysis.model_dump(mode="json"), analysis_before)
        self.assertEqual(discovery.model_dump(mode="json"), discovery_before)
        self.assertEqual(adaptation_result.model_dump(mode="json"), adaptation_before)


class EmbeddedGenerationIntegrationTest(unittest.TestCase):
    def test_service_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        adaptation_result = _adaptation_result_for(analysis, discovery)
        result = GenerationService.default().execute(analysis, discovery, adaptation_result)
        self.assertTrue(result.generation_plan.generation_required)

    def test_workflow_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertTrue(strategy.generation_plan.generation_required)
        self.assertGreater(len(strategy.generation_plan.modules_to_generate), 0)


class EmbeddedGenerationProviderParityTest(unittest.TestCase):
    def test_provider_matches_decide_generation(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        adaptation_result = _adaptation_result_for(analysis, discovery)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_generation(
            facts,
            dimensions,
            adaptation_result.strategy,
            adaptation_result.resource_bindings,
            adaptation_result.reuse_plan,
            adaptation_result.adaptation_plan,
        )
        provider = EmbeddedGenerationProvider().execute(analysis, discovery, adaptation_result)
        self.assertEqual(decision.generation_required, provider.generation_plan.generation_required)
        self.assertEqual(decision.generation_scope, provider.generation_plan.generation_scope)
        self.assertEqual(
            [target.model_dump() for target in decision.modules_to_generate],
            [target.model_dump() for target in provider.generation_plan.modules_to_generate],
        )


if __name__ == "__main__":
    unittest.main()
