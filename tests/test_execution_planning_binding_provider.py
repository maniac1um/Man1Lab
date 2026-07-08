"""Tests for Embedded Resource Binding Provider and Decision Foundation — Phase 6.2."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path

from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution_planning_runtime import StrategyDecisionResult, StrategyDecisionSnapshot
from models.execution_strategy import BindingRole, ScopeCommitment, StrategyPosture, UsageIntent
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    AnalysisReference,
    CandidateResources,
    CollectionSource,
    CollectionSourceType,
    DiscoveryGaps,
    DiscoveryMetadata,
    DiscoveryProvider,
    DiscoveryStatus,
    NeedCategory,
    Officiality,
    RepositoryCandidate,
    ResearchResourceDiscovery,
    ResourceIdentity,
    ResourceNeed,
    ResourceType,
    SelectionRecord,
    SelectionResult,
    VerificationCollection,
    VerificationRecord,
    VerificationStatus,
)
from providers.embedded.decision_foundation import (
    build_observed_facts,
    evaluate_dimensions,
)
from providers.embedded.decision_foundation.strategy_decision import decide_strategy
from providers.embedded.resource_binding import EmbeddedResourceBindingProvider
from providers.embedded.strategy import EmbeddedStrategyProvider
from services.execution_planning.resource_binding_service import ResourceBindingService
from tests.fixtures import sample_reproduction_analysis
from tests.test_execution_planning_strategy_provider import (
    _discovery_greenfield,
    _discovery_hybrid,
    _discovery_reuse,
    _repository_candidate,
    _repository_selection,
    _verification_record,
)


def _base_discovery(analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
    return ResearchResourceDiscovery(
        metadata=DiscoveryMetadata(
            discovery_id="disc-bind",
            created_at=datetime.now(UTC),
            status=DiscoveryStatus.COMPLETE,
        ),
        analysis_reference=AnalysisReference(
            analysis_schema_version="1.0",
            paper_title=analysis.metadata.title,
            analysis_content_hash="hash",
        ),
    )


def _typed_candidate(
    *,
    candidate_id: str,
    need_id: str,
    resource_type: ResourceType,
    officiality: Officiality = Officiality.UNKNOWN,
) -> RepositoryCandidate:
    return RepositoryCandidate(
        candidate_id=candidate_id,
        identity=ResourceIdentity(
            provider=DiscoveryProvider.PAPER_LINK,
            provider_native_id=candidate_id,
            normalized_url=f"https://example.com/{candidate_id}",
        ),
        provider=DiscoveryProvider.PAPER_LINK,
        resource_type=resource_type,
        officiality=officiality,
        url=f"https://example.com/{candidate_id}",
        collection_source=CollectionSource(source_type=CollectionSourceType.ANALYSIS_EXTERNAL_RESOURCE),
        addresses_needs=[need_id],
    )


def _selection(
    *,
    selection_id: str,
    need_id: str,
    category: NeedCategory,
    primary_candidate_id: str,
    fallback_candidate_ids: list[str] | None = None,
) -> SelectionRecord:
    return SelectionRecord(
        selection_id=selection_id,
        resource_need=ResourceNeed(
            need_id=need_id,
            need_category=category,
            description=category.value,
        ),
        primary_candidate_id=primary_candidate_id,
        fallback_candidate_ids=fallback_candidate_ids or [],
    )


def _discovery_full_bindings(analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
    repo = _typed_candidate(
        candidate_id="candidate-repo",
        need_id="need-repo",
        resource_type=ResourceType.OFFICIAL_REPOSITORY,
        officiality=Officiality.OFFICIAL,
    )
    checkpoint = _typed_candidate(
        candidate_id="candidate-ckpt",
        need_id="need-ckpt",
        resource_type=ResourceType.CHECKPOINT,
    )
    dataset = _typed_candidate(
        candidate_id="candidate-data",
        need_id="need-data",
        resource_type=ResourceType.DATASET_PORTAL,
    )
    fallback = _typed_candidate(
        candidate_id="candidate-fallback",
        need_id="need-repo",
        resource_type=ResourceType.COMMUNITY_REPOSITORY,
        officiality=Officiality.COMMUNITY,
    )
    return _base_discovery(analysis).model_copy(
        update={
            "candidate_resources": CandidateResources(
                candidates=[repo, checkpoint, dataset, fallback],
            ),
            "verification": VerificationCollection(
                records=[
                    _verification_record("candidate-repo", status=VerificationStatus.PASS),
                    _verification_record("candidate-ckpt", status=VerificationStatus.PASS),
                    _verification_record("candidate-data", status=VerificationStatus.PASS),
                    _verification_record("candidate-fallback", status=VerificationStatus.PASS),
                ]
            ),
            "selection": SelectionResult(
                selections=[
                    _selection(
                        selection_id="selection-repo",
                        need_id="need-repo",
                        category=NeedCategory.CODE_REPOSITORY,
                        primary_candidate_id="candidate-repo",
                        fallback_candidate_ids=["candidate-fallback"],
                    ),
                    _selection(
                        selection_id="selection-ckpt",
                        need_id="need-ckpt",
                        category=NeedCategory.CHECKPOINT,
                        primary_candidate_id="candidate-ckpt",
                    ),
                    _selection(
                        selection_id="selection-data",
                        need_id="need-data",
                        category=NeedCategory.DATASET,
                        primary_candidate_id="candidate-data",
                    ),
                ]
            ),
            "discovery_gaps": DiscoveryGaps(gaps=[]),
        }
    )


def _discovery_unverified_repo(analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
    candidate = _repository_candidate()
    return _base_discovery(analysis).model_copy(
        update={
            "candidate_resources": CandidateResources(candidates=[candidate]),
            "verification": VerificationCollection(
                records=[_verification_record(candidate.candidate_id, status=VerificationStatus.FAIL)]
            ),
            "selection": SelectionResult(selections=[_repository_selection(candidate.candidate_id)]),
            "discovery_gaps": DiscoveryGaps(gaps=[]),
        }
    )


def _reuse_strategy_result() -> StrategyDecisionResult:
    return StrategyDecisionResult(
        strategy=StrategyDecisionSnapshot(
            primary_posture=StrategyPosture.OFFICIAL_REPOSITORY,
            scope_commitment=ScopeCommitment.NARROWED_SCOPE,
            rationale="Verified official implementation satisfies required resources.",
        )
    )


class DecisionFoundationTest(unittest.TestCase):
    def test_build_observed_facts_from_discovery(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        facts = build_observed_facts(analysis, _discovery_full_bindings(analysis))
        self.assertTrue(facts.repository_available)
        self.assertTrue(facts.checkpoint_available)
        self.assertTrue(facts.dataset_available)

    def test_evaluate_dimensions_produces_enum_levels(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        facts = build_observed_facts(analysis, _discovery_reuse(analysis))
        dimensions = evaluate_dimensions(facts)
        self.assertEqual(dimensions.resource_sufficiency.value, "high")
        self.assertEqual(dimensions.reuse_opportunity.value, "high")


class StrategyRefactorPreservationTest(unittest.TestCase):
    def test_strategy_provider_behavior_unchanged_for_reuse(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_reuse(analysis)
        result = EmbeddedStrategyProvider().execute(analysis, discovery)
        self.assertEqual(result.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)
        self.assertIn("rule:reuse", result.strategy.deciding_factors)
        self.assertIn("dimension:resource_sufficiency:high", result.strategy.deciding_factors)

    def test_strategy_provider_behavior_unchanged_for_hybrid_and_greenfield(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        hybrid = EmbeddedStrategyProvider().execute(analysis, _discovery_hybrid(analysis))
        greenfield = EmbeddedStrategyProvider().execute(analysis, _discovery_greenfield(analysis))
        self.assertEqual(hybrid.strategy.primary_posture, StrategyPosture.HYBRID)
        self.assertEqual(greenfield.strategy.primary_posture, StrategyPosture.GREENFIELD)

    def test_decide_strategy_matches_provider_output(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_reuse(analysis)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_strategy(facts, dimensions)
        provider = EmbeddedStrategyProvider().execute(analysis, discovery)
        self.assertEqual(decision.primary_posture, provider.strategy.primary_posture)
        self.assertEqual(decision.scope_commitment, provider.strategy.scope_commitment)
        self.assertEqual(decision.rationale, provider.strategy.rationale)


class EmbeddedResourceBindingProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        self.provider = EmbeddedResourceBindingProvider()

    def test_primary_repository_binding(self) -> None:
        discovery = _discovery_reuse(self.analysis)
        strategy = _reuse_strategy_result()
        result = self.provider.execute(self.analysis, discovery, strategy)
        roles = {binding.role for binding in result.resource_bindings.bindings}
        self.assertIn(BindingRole.PRIMARY_REPOSITORY, roles)

    def test_checkpoint_binding(self) -> None:
        discovery = _discovery_full_bindings(self.analysis)
        strategy = _reuse_strategy_result()
        result = self.provider.execute(self.analysis, discovery, strategy)
        checkpoint_bindings = [
            b for b in result.resource_bindings.bindings if b.role == BindingRole.CHECKPOINT
        ]
        self.assertEqual(len(checkpoint_bindings), 1)
        self.assertEqual(checkpoint_bindings[0].candidate_id, "candidate-ckpt")

    def test_dataset_binding(self) -> None:
        discovery = _discovery_full_bindings(self.analysis)
        strategy = _reuse_strategy_result()
        result = self.provider.execute(self.analysis, discovery, strategy)
        dataset_bindings = [
            b for b in result.resource_bindings.bindings if b.role == BindingRole.DATASET
        ]
        self.assertEqual(len(dataset_bindings), 1)

    def test_supporting_resource_binding(self) -> None:
        discovery = _discovery_full_bindings(self.analysis)
        strategy = _reuse_strategy_result()
        result = self.provider.execute(self.analysis, discovery, strategy)
        fallback_bindings = [
            b for b in result.resource_bindings.bindings if b.role == BindingRole.FALLBACK_REPOSITORY
        ]
        self.assertEqual(len(fallback_bindings), 1)
        self.assertEqual(fallback_bindings[0].usage_intent, UsageIntent.FALLBACK_IF_PRIMARY_FAILS)

    def test_unverified_resources_not_primary(self) -> None:
        discovery = _discovery_unverified_repo(self.analysis)
        strategy = _reuse_strategy_result()
        result = self.provider.execute(self.analysis, discovery, strategy)
        self.assertEqual(result.resource_bindings.bindings, [])

    def test_deterministic_bindings(self) -> None:
        discovery = _discovery_full_bindings(self.analysis)
        strategy = _reuse_strategy_result()
        first = self.provider.execute(self.analysis, discovery, strategy)
        second = self.provider.execute(self.analysis, discovery, strategy)
        self.assertEqual(
            [binding.model_dump() for binding in first.resource_bindings.bindings],
            [binding.model_dump() for binding in second.resource_bindings.bindings],
        )

    def test_binding_rationale_and_notes(self) -> None:
        discovery = _discovery_full_bindings(self.analysis)
        strategy = _reuse_strategy_result()
        result = self.provider.execute(self.analysis, discovery, strategy)
        self.assertIn("Evaluating discovery selections", result.decision_notes)
        self.assertTrue(result.resource_bindings.combination_rationale)
        self.assertTrue(any(binding.binding_rationale for binding in result.resource_bindings.bindings))

    def test_immutable_inputs(self) -> None:
        discovery = _discovery_full_bindings(self.analysis)
        strategy = _reuse_strategy_result()
        analysis_before = self.analysis.model_dump(mode="json")
        discovery_before = discovery.model_dump(mode="json")
        strategy_before = strategy.model_dump(mode="json")
        self.provider.execute(self.analysis, discovery, strategy)
        self.assertEqual(self.analysis.model_dump(mode="json"), analysis_before)
        self.assertEqual(discovery.model_dump(mode="json"), discovery_before)
        self.assertEqual(strategy.model_dump(mode="json"), strategy_before)


class EmbeddedResourceBindingIntegrationTest(unittest.TestCase):
    def test_service_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_full_bindings(analysis)
        strategy = EmbeddedStrategyProvider().execute(analysis, discovery)
        result = ResourceBindingService.default().execute(analysis, discovery, strategy)
        self.assertGreater(len(result.resource_bindings.bindings), 0)

    def test_workflow_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_full_bindings(analysis)
        execution_strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertGreater(len(execution_strategy.resource_bindings.bindings), 0)
        self.assertIsNotNone(execution_strategy.resource_bindings.anchor_binding_id)


if __name__ == "__main__":
    unittest.main()
