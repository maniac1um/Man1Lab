"""Tests for Embedded Risk Provider and Decision Foundation risk — Phase 6.6."""

from __future__ import annotations

import unittest
from pathlib import Path

from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution_planning_runtime import GenerationPlanSnapshot
from models.execution_strategy import (
    GenerationScope,
    PlanningStatus,
    RiskSeverity,
    ReuseMode,
    StrategyPosture,
)
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    CandidateResources,
    DiscoveryGap,
    DiscoveryGapType,
    DiscoveryGaps,
    GapSeverity,
    ResearchResourceDiscovery,
    SelectionResult,
    VerificationCollection,
    VerificationStatus,
)
from providers.embedded.decision_foundation import (
    build_observed_facts,
    decide_risk,
    evaluate_dimensions,
    evaluate_execution_readiness,
)
from providers.embedded.generation import EmbeddedGenerationProvider
from providers.embedded.resource_binding import EmbeddedResourceBindingProvider
from providers.embedded.reuse import EmbeddedReuseProvider
from providers.embedded.risk import EmbeddedRiskProvider
from providers.embedded.strategy import EmbeddedStrategyProvider
from services.execution_planning.risk_service import RiskService
from tests.fixtures import sample_reproduction_analysis
from tests.test_execution_planning_strategy_provider import (
    _base_discovery,
    _discovery_greenfield,
    _discovery_hybrid,
    _discovery_reuse,
    _repository_candidate,
    _repository_selection,
    _verification_record,
)
from providers.embedded.adaptation import EmbeddedAdaptationProvider


def _reuse_result_for(analysis: PaperReproductionAnalysis, discovery: ResearchResourceDiscovery):
    strategy = EmbeddedStrategyProvider().execute(analysis, discovery)
    binding = EmbeddedResourceBindingProvider().execute(analysis, discovery, strategy)
    return EmbeddedReuseProvider().execute(analysis, discovery, binding)


def _adaptation_result_for(analysis: PaperReproductionAnalysis, discovery: ResearchResourceDiscovery):
    reuse_result = _reuse_result_for(analysis, discovery)
    return EmbeddedAdaptationProvider().execute(analysis, discovery, reuse_result)


def _generation_result_for(analysis: PaperReproductionAnalysis, discovery: ResearchResourceDiscovery):
    adaptation_result = _adaptation_result_for(analysis, discovery)
    return EmbeddedGenerationProvider().execute(analysis, discovery, adaptation_result)


def _discovery_archived_repo(analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
    candidate = _repository_candidate()
    return _base_discovery(analysis).model_copy(
        update={
            "candidate_resources": CandidateResources(candidates=[candidate]),
            "verification": VerificationCollection(
                records=[_verification_record(candidate.candidate_id, status=VerificationStatus.PASS)]
            ),
            "selection": SelectionResult(selections=[_repository_selection(candidate.candidate_id)]),
            "discovery_gaps": DiscoveryGaps(
                gaps=[
                    DiscoveryGap(
                        gap_id="gap-archived",
                        gap_type=DiscoveryGapType.REPOSITORY_ARCHIVED,
                        severity=GapSeverity.DEGRADED,
                        description="Repository archived",
                    )
                ]
            ),
        }
    )


class DecisionFoundationRiskTest(unittest.TestCase):
    def test_execution_readiness_assessment(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_reuse(analysis)
        generation_result = _generation_result_for(analysis, discovery)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        readiness = evaluate_execution_readiness(
            facts,
            dimensions,
            generation_result.strategy,
            generation_result.resource_bindings,
            generation_result.reuse_plan,
            generation_result.adaptation_plan,
            generation_result.generation_plan,
        )
        self.assertEqual(readiness.resource_ready.value, "ready")
        self.assertEqual(readiness.engineering_ready.value, "ready")

    def test_decide_risk_uses_shared_facts_and_dimensions(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        generation_result = _generation_result_for(analysis, discovery)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        readiness = evaluate_execution_readiness(
            facts,
            dimensions,
            generation_result.strategy,
            generation_result.resource_bindings,
            generation_result.reuse_plan,
            generation_result.adaptation_plan,
            generation_result.generation_plan,
        )
        decision = decide_risk(
            facts,
            dimensions,
            readiness,
            generation_result.strategy,
            generation_result.resource_bindings,
            generation_result.reuse_plan,
            generation_result.adaptation_plan,
            generation_result.generation_plan,
        )
        self.assertIn("dimension:resource_sufficiency", decision.provider_factors[4])


class EmbeddedRiskProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        self.provider = EmbeddedRiskProvider()

    def _execute(self, discovery: ResearchResourceDiscovery):
        generation_result = _generation_result_for(self.analysis, discovery)
        return self.provider.execute(self.analysis, discovery, generation_result), generation_result

    def test_greenfield_produces_implementation_risks(self) -> None:
        result, generation_result = self._execute(_discovery_greenfield(self.analysis))
        self.assertEqual(generation_result.strategy.primary_posture, StrategyPosture.GREENFIELD)
        risk_ids = {risk.risk_id for risk in result.risk_assessment.degraded_risks}
        self.assertIn("risk-engineering-greenfield", risk_ids)
        self.assertLess(result.risk_assessment.overall_confidence, 0.7)

    def test_hybrid_produces_integration_risks(self) -> None:
        result, _ = self._execute(_discovery_hybrid(self.analysis))
        risk_ids = {risk.risk_id for risk in result.risk_assessment.degraded_risks}
        self.assertIn("risk-integration-hybrid", risk_ids)

    def test_official_repository_produces_reduced_risks(self) -> None:
        result, generation_result = self._execute(_discovery_reuse(self.analysis))
        self.assertEqual(generation_result.reuse_plan.reuse_mode, ReuseMode.AS_IS)
        info_ids = {risk.risk_id for risk in result.risk_assessment.informational_risks}
        self.assertIn("risk-info-official-repository", info_ids)
        self.assertGreater(result.risk_assessment.overall_confidence, 0.8)

    def test_archived_repository_risk(self) -> None:
        result, _ = self._execute(_discovery_archived_repo(self.analysis))
        risk_ids = {risk.risk_id for risk in result.risk_assessment.degraded_risks}
        self.assertIn("risk-repository-archived", risk_ids)

    def test_missing_generation_targets(self) -> None:
        discovery = _discovery_hybrid(self.analysis)
        generation_result = _generation_result_for(self.analysis, discovery)
        facts = build_observed_facts(self.analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        empty_generation = GenerationPlanSnapshot(
            generation_required=True,
            generation_scope=GenerationScope.MISSING_MODULES,
            modules_to_generate=[],
        )
        readiness = evaluate_execution_readiness(
            facts,
            dimensions,
            generation_result.strategy,
            generation_result.resource_bindings,
            generation_result.reuse_plan,
            generation_result.adaptation_plan,
            empty_generation,
        )
        decision = decide_risk(
            facts,
            dimensions,
            readiness,
            generation_result.strategy,
            generation_result.resource_bindings,
            generation_result.reuse_plan,
            generation_result.adaptation_plan,
            empty_generation,
        )
        risk_ids = {risk.risk_id for risk in decision.degraded_risks}
        self.assertIn("risk-execution-generation-gap", risk_ids)

    def test_blocking_risk_creation(self) -> None:
        result, _ = self._execute(_discovery_hybrid(self.analysis))
        self.assertGreater(len(result.risk_assessment.blocking_risks), 0)
        self.assertEqual(result.risk_assessment.blocking_risks[0].severity, RiskSeverity.BLOCKING)

    def test_fallback_strategy_generation(self) -> None:
        result, _ = self._execute(_discovery_hybrid(self.analysis))
        self.assertGreater(len(result.risk_assessment.fallback_strategies), 0)
        self.assertTrue(result.risk_assessment.fallback_strategies[0].trigger_condition)

    def test_deterministic_execution(self) -> None:
        discovery = _discovery_hybrid(self.analysis)
        generation_result = _generation_result_for(self.analysis, discovery)
        first = self.provider.execute(self.analysis, discovery, generation_result)
        second = self.provider.execute(self.analysis, discovery, generation_result)
        self.assertEqual(first.risk_assessment.model_dump(), second.risk_assessment.model_dump())
        self.assertEqual(first.decision_notes, second.decision_notes)

    def test_rationale_generation(self) -> None:
        result, _ = self._execute(_discovery_hybrid(self.analysis))
        self.assertIn("Risk assessment for", result.decision_notes)

    def test_decision_notes(self) -> None:
        result, _ = self._execute(_discovery_hybrid(self.analysis))
        self.assertIn("execution_ready", result.diagnostics)
        self.assertIn("Execution readiness", result.decision_notes)

    def test_immutable_inputs(self) -> None:
        discovery = _discovery_hybrid(self.analysis)
        generation_result = _generation_result_for(self.analysis, discovery)
        analysis_before = self.analysis.model_dump(mode="json")
        discovery_before = discovery.model_dump(mode="json")
        generation_before = generation_result.model_dump(mode="json")
        self.provider.execute(self.analysis, discovery, generation_result)
        self.assertEqual(self.analysis.model_dump(mode="json"), analysis_before)
        self.assertEqual(discovery.model_dump(mode="json"), discovery_before)
        self.assertEqual(generation_result.model_dump(mode="json"), generation_before)


class EmbeddedRiskIntegrationTest(unittest.TestCase):
    def test_service_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        generation_result = _generation_result_for(analysis, discovery)
        result = RiskService.default().execute(analysis, discovery, generation_result)
        self.assertGreater(result.risk_assessment.overall_confidence, 0.0)

    def test_workflow_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertGreater(len(strategy.risk_assessment.degraded_risks), 0)
        self.assertIn(
            strategy.metadata.status,
            {PlanningStatus.PARTIAL.value, PlanningStatus.DEGRADED.value},
        )


class EmbeddedRiskProviderParityTest(unittest.TestCase):
    def test_provider_matches_decide_risk(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        generation_result = _generation_result_for(analysis, discovery)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        readiness = evaluate_execution_readiness(
            facts,
            dimensions,
            generation_result.strategy,
            generation_result.resource_bindings,
            generation_result.reuse_plan,
            generation_result.adaptation_plan,
            generation_result.generation_plan,
        )
        decision = decide_risk(
            facts,
            dimensions,
            readiness,
            generation_result.strategy,
            generation_result.resource_bindings,
            generation_result.reuse_plan,
            generation_result.adaptation_plan,
            generation_result.generation_plan,
        )
        provider = EmbeddedRiskProvider().execute(analysis, discovery, generation_result)
        self.assertEqual(decision.overall_confidence, provider.risk_assessment.overall_confidence)
        self.assertEqual(
            [risk.model_dump() for risk in decision.blocking_risks],
            [risk.model_dump() for risk in provider.risk_assessment.blocking_risks],
        )
        self.assertEqual(
            [risk.model_dump() for risk in decision.degraded_risks],
            [risk.model_dump() for risk in provider.risk_assessment.degraded_risks],
        )


if __name__ == "__main__":
    unittest.main()
