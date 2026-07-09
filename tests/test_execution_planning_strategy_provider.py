"""Tests for Embedded Strategy Provider — Phase 6.1."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path

from discovery.empty import build_empty_discovery
from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution_strategy import ScopeCommitment, StrategyPosture
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    AnalysisReference,
    CandidateResources,
    CollectionSource,
    CollectionSourceType,
    DiscoveryGap,
    DiscoveryGapType,
    DiscoveryGaps,
    DiscoveryMetadata,
    DiscoveryProvider,
    DiscoveryStatus,
    GapSeverity,
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
from providers.embedded.strategy import EmbeddedStrategyProvider
from providers.noop.strategy import NoOpStrategyProvider
from services.execution_planning.strategy_service import StrategyService
from tests.fixtures import sample_reproduction_analysis


def _base_discovery(analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
    return ResearchResourceDiscovery(
        metadata=DiscoveryMetadata(
            discovery_id="disc-test",
            created_at=datetime.now(UTC),
            status=DiscoveryStatus.COMPLETE,
        ),
        analysis_reference=AnalysisReference(
            analysis_schema_version="1.0",
            paper_title=analysis.metadata.title,
            analysis_content_hash="hash",
        ),
    )


def _repository_candidate(
    *,
    candidate_id: str = "candidate-repo",
    resource_type: ResourceType = ResourceType.OFFICIAL_REPOSITORY,
    officiality: Officiality = Officiality.OFFICIAL,
) -> RepositoryCandidate:
    return RepositoryCandidate(
        candidate_id=candidate_id,
        identity=ResourceIdentity(
            provider=DiscoveryProvider.PAPER_LINK,
            provider_native_id=candidate_id,
            normalized_url="https://example.com/repo",
        ),
        provider=DiscoveryProvider.PAPER_LINK,
        resource_type=resource_type,
        officiality=officiality,
        url="https://example.com/repo",
        collection_source=CollectionSource(source_type=CollectionSourceType.ANALYSIS_EXTERNAL_RESOURCE),
        addresses_needs=["need-repo"],
    )


def _repository_selection(candidate_id: str) -> SelectionRecord:
    return SelectionRecord(
        selection_id="selection-repo",
        resource_need=ResourceNeed(
            need_id="need-repo",
            need_category=NeedCategory.CODE_REPOSITORY,
            description="Official repository",
        ),
        primary_candidate_id=candidate_id,
    )


def _verification_record(
    candidate_id: str,
    *,
    status: VerificationStatus,
) -> VerificationRecord:
    return VerificationRecord(
        verification_id=f"verify-{candidate_id}",
        candidate_id=candidate_id,
        status=status,
        verified_at=datetime.now(UTC),
    )


def _discovery_reuse(analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
    candidate = _repository_candidate()
    return _base_discovery(analysis).model_copy(
        update={
            "candidate_resources": CandidateResources(candidates=[candidate]),
            "verification": VerificationCollection(
                records=[_verification_record(candidate.candidate_id, status=VerificationStatus.PASS)]
            ),
            "selection": SelectionResult(selections=[_repository_selection(candidate.candidate_id)]),
            "discovery_gaps": DiscoveryGaps(gaps=[]),
        }
    )


def _discovery_hybrid(analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
    candidate = _repository_candidate()
    return _base_discovery(analysis).model_copy(
        update={
            "metadata": DiscoveryMetadata(
                discovery_id="disc-test",
                created_at=datetime.now(UTC),
                status=DiscoveryStatus.PARTIAL,
            ),
            "candidate_resources": CandidateResources(candidates=[candidate]),
            "verification": VerificationCollection(
                records=[_verification_record(candidate.candidate_id, status=VerificationStatus.PASS)]
            ),
            "selection": SelectionResult(selections=[_repository_selection(candidate.candidate_id)]),
            "discovery_gaps": DiscoveryGaps(
                gaps=[
                    DiscoveryGap(
                        gap_id="gap-checkpoint",
                        gap_type=DiscoveryGapType.CHECKPOINT_MISSING,
                        severity=GapSeverity.BLOCKING,
                        description="Checkpoint unavailable",
                    )
                ]
            ),
        }
    )


def _discovery_greenfield(analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
    return build_empty_discovery(analysis)


class EmbeddedStrategyProviderDecisionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        self.provider = EmbeddedStrategyProvider()

    def test_reuse_decision(self) -> None:
        discovery = _discovery_reuse(self.analysis)
        result = self.provider.execute(self.analysis, discovery)
        self.assertEqual(result.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)
        self.assertEqual(result.strategy.scope_commitment, ScopeCommitment.NARROWED_SCOPE)
        self.assertIn("rule:reuse", result.strategy.deciding_factors)
        self.assertIn("invocation_reason:discovery_complete", result.strategy.deciding_factors)

    def test_hybrid_decision(self) -> None:
        discovery = _discovery_hybrid(self.analysis)
        result = self.provider.execute(self.analysis, discovery)
        self.assertEqual(result.strategy.primary_posture, StrategyPosture.HYBRID)
        self.assertEqual(result.strategy.scope_commitment, ScopeCommitment.PARTIAL_REPRODUCTION)
        self.assertIn("rule:hybrid", result.strategy.deciding_factors)
        self.assertIn("invocation_reason:discovery_partial", result.strategy.deciding_factors)

    def test_official_usable_partial_no_gaps(self) -> None:
        from datetime import UTC, datetime
        from pathlib import Path

        from models.research_resource_discovery import (
            AnalysisReference,
            CandidateResources,
            CollectionSource,
            CollectionSourceType,
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
        from tests.fixtures import sample_reproduction_analysis

        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        candidate = _repository_candidate()
        discovery = ResearchResourceDiscovery(
            metadata=DiscoveryMetadata(
                discovery_id="disc-test",
                created_at=datetime.now(UTC),
                status=DiscoveryStatus.COMPLETE,
            ),
            analysis_reference=AnalysisReference(
                analysis_schema_version="1.0",
                paper_title=analysis.metadata.title,
                analysis_content_hash="hash",
            ),
            candidate_resources=CandidateResources(candidates=[candidate]),
            verification=VerificationCollection(
                records=[_verification_record(candidate.candidate_id, status=VerificationStatus.PARTIAL)]
            ),
            selection=SelectionResult(
                selections=[
                    SelectionRecord(
                        selection_id="selection-repo",
                        resource_need=ResourceNeed(
                            need_id="need-repo",
                            need_category=NeedCategory.CODE_REPOSITORY,
                            description="Official repository",
                        ),
                        primary_candidate_id=candidate.candidate_id,
                        confidence=0.65,
                    )
                ]
            ),
        )
        result = self.provider.execute(analysis, discovery)
        self.assertEqual(result.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)
        self.assertIn("rule:official_usable", result.strategy.deciding_factors)

    def test_greenfield_decision(self) -> None:
        discovery = _discovery_greenfield(self.analysis)
        result = self.provider.execute(self.analysis, discovery)
        self.assertEqual(result.strategy.primary_posture, StrategyPosture.GREENFIELD)
        self.assertEqual(result.strategy.scope_commitment, ScopeCommitment.FULL_REPRODUCTION)
        self.assertIn("rule:greenfield", result.strategy.deciding_factors)
        self.assertIn("invocation_reason:insufficient_discovery", result.strategy.deciding_factors)


class EmbeddedStrategyProviderOutputTest(unittest.TestCase):
    def test_rationale_generation(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        result = EmbeddedStrategyProvider().execute(analysis, _discovery_reuse(analysis))
        self.assertIn("Verified official implementation", result.strategy.rationale)

    def test_decision_notes(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        result = EmbeddedStrategyProvider().execute(analysis, _discovery_hybrid(analysis))
        self.assertIn("Repository candidate detected", result.decision_notes)
        self.assertIn("Required gap:", result.decision_notes)
        self.assertIn("HYBRID", result.decision_notes)

    def test_stage_runtime_metadata(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        result = EmbeddedStrategyProvider().execute(analysis, _discovery_hybrid(analysis))
        self.assertIsNotNone(result.started_at)
        self.assertIsNotNone(result.completed_at)
        self.assertEqual(result.stage_status.value, "success")
        self.assertTrue(result.warnings)


class EmbeddedStrategyProviderDeterminismTest(unittest.TestCase):
    def test_deterministic_execution(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_reuse(analysis)
        first = EmbeddedStrategyProvider().execute(analysis, discovery)
        second = EmbeddedStrategyProvider().execute(analysis, discovery)
        self.assertEqual(first.strategy.model_dump(), second.strategy.model_dump())
        self.assertEqual(first.decision_notes, second.decision_notes)


class EmbeddedStrategyProviderIntegrationTest(unittest.TestCase):
    def test_service_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_reuse(analysis)
        result = StrategyService.default().execute(analysis, discovery)
        self.assertEqual(result.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)

    def test_provider_ordering_prefers_embedded(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_reuse(analysis)
        service = StrategyService(
            providers=[EmbeddedStrategyProvider(), NoOpStrategyProvider()],
        )
        result = service.execute(analysis, discovery)
        self.assertIn("rule:reuse", result.strategy.deciding_factors)

    def test_workflow_integration(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_reuse(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)

    def test_immutable_analysis_and_discovery(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = _discovery_hybrid(analysis)
        analysis_before = analysis.model_dump(mode="json")
        discovery_before = discovery.model_dump(mode="json")
        EmbeddedStrategyProvider().execute(analysis, discovery)
        self.assertEqual(analysis.model_dump(mode="json"), analysis_before)
        self.assertEqual(discovery.model_dump(mode="json"), discovery_before)


if __name__ == "__main__":
    unittest.main()
