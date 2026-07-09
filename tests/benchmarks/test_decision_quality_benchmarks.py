"""Regression tests for discovery and planning decision quality."""

from __future__ import annotations

import unittest

from discovery.workflow import DiscoveryWorkflow
from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution_strategy import StrategyPosture
from models.research_resource_discovery import NeedCategory
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from providers.noop.collection import NoOpCollectionProvider
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from providers.noop.noop_ranking_provider import NoOpRankingProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService
from tests.benchmarks.fixtures import benchmark_cases, repository_selection_confidence


def _embedded_discovery_workflow() -> DiscoveryWorkflow:
    return DiscoveryWorkflow(
        collection_service=CollectionService(
            providers=[EmbeddedResourceProvider(), NoOpCollectionProvider()]
        ),
        evidence_service=EvidenceService(
            providers=[EmbeddedEvidenceProvider(), NoOpEvidenceProvider()]
        ),
        verification_service=VerificationService(
            providers=[EmbeddedVerificationProvider(), NoOpVerificationProvider()]
        ),
        ranking_service=RankingService(
            providers=[EmbeddedRankingProvider(), NoOpRankingProvider()]
        ),
    )


class DecisionQualityBenchmarkTest(unittest.TestCase):
    def test_benchmark_suite(self) -> None:
        workflow = _embedded_discovery_workflow()
        planning = ExecutionPlanningWorkflow.default()

        for case in benchmark_cases():
            with self.subTest(case=case.name):
                analysis = case.analysis_factory()
                discovery = workflow.run(analysis)
                strategy = planning.run(analysis, discovery)
                expectation = case.expectation

                if expectation.min_selection_count:
                    self.assertGreaterEqual(
                        discovery.metadata.selection_count,
                        expectation.min_selection_count,
                        msg=f"{case.name}: expected selections",
                    )

                repo_confidence = repository_selection_confidence(discovery)
                if expectation.require_repository_selection:
                    repo_selections = [
                        item
                        for item in discovery.selection.selections
                        if item.resource_need.need_category == NeedCategory.CODE_REPOSITORY
                        and item.primary_candidate_id
                    ]
                    self.assertTrue(repo_selections, msg=f"{case.name}: repository not selected")
                if expectation.min_repository_confidence:
                    self.assertGreaterEqual(
                        repo_confidence,
                        expectation.min_repository_confidence,
                        msg=f"{case.name}: confidence too low ({repo_confidence})",
                    )

                posture = strategy.strategy.primary_posture
                if expectation.posture is not None:
                    self.assertEqual(posture, expectation.posture, msg=case.name)
                if expectation.allowed_postures is not None:
                    self.assertIn(posture, expectation.allowed_postures, msg=case.name)
                if expectation.forbid_posture is not None:
                    self.assertNotEqual(posture, expectation.forbid_posture, msg=case.name)

                if expectation.min_bindings:
                    self.assertGreaterEqual(
                        len(strategy.resource_bindings.bindings),
                        expectation.min_bindings,
                        msg=f"{case.name}: insufficient bindings",
                    )

                if expectation.reuse_mode is not None:
                    self.assertEqual(
                        strategy.reuse_plan.reuse_mode,
                        expectation.reuse_mode,
                        msg=f"{case.name}: reuse mode",
                    )

                if expectation.generation_required is not None:
                    self.assertEqual(
                        strategy.generation_plan.generation_required,
                        expectation.generation_required,
                        msg=f"{case.name}: generation_required",
                    )


class OfficialRepoNotGreenfieldRegressionTest(unittest.TestCase):
    def test_official_repo_partial_verification_not_greenfield(self) -> None:
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
        candidate = RepositoryCandidate(
            candidate_id="candidate-repo",
            identity=ResourceIdentity(
                provider=DiscoveryProvider.PAPER_LINK,
                provider_native_id="org/repo",
                normalized_url="https://example.com/repo",
            ),
            provider=DiscoveryProvider.PAPER_LINK,
            resource_type=ResourceType.OFFICIAL_REPOSITORY,
            officiality=Officiality.OFFICIAL,
            url="https://example.com/repo",
            collection_source=CollectionSource(source_type=CollectionSourceType.ANALYSIS_EXTERNAL_RESOURCE),
            addresses_needs=["need-repo"],
        )
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
                records=[
                    VerificationRecord(
                        verification_id="verify-repo",
                        candidate_id=candidate.candidate_id,
                        status=VerificationStatus.PARTIAL,
                        verified_at=datetime.now(UTC),
                    )
                ]
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
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)
        self.assertNotEqual(strategy.strategy.primary_posture, StrategyPosture.GREENFIELD)
        self.assertGreaterEqual(len(strategy.resource_bindings.bindings), 1)


if __name__ == "__main__":
    unittest.main()
