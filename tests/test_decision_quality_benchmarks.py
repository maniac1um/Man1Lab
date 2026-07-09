"""Golden benchmark regression tests for Discovery and Execution Planning decisions."""

from __future__ import annotations

import unittest

from discovery.decision_trace import build_discovery_decision_trace
from discovery.workflow import DiscoveryWorkflow
from execution_planning.decision_trace import build_planning_decision_trace
from execution_planning.execution_graph import build_execution_graph
from execution_planning.workflow import ExecutionPlanningWorkflow
from models.decision_trace import DecisionStageName
from models.execution_strategy import PlanningStatus, StrategyPosture
from models.research_resource_discovery import ResearchAssetType
from providers.embedded.decision_foundation.risk_decision import ReadinessLevel
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
from tests.benchmarks.golden.fixtures import (
    GOLDEN_BENCHMARKS,
    repository_selection,
)


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


class GoldenBenchmarkRegressionTest(unittest.TestCase):
    def test_all_golden_benchmarks(self) -> None:
        workflow = _embedded_discovery_workflow()
        planning = ExecutionPlanningWorkflow.default()

        for expectation, analysis_builder in GOLDEN_BENCHMARKS:
            with self.subTest(benchmark=expectation.name):
                analysis = analysis_builder()
                discovery = workflow.run(analysis)
                strategy = planning.run(analysis, discovery)

                repo_selection = repository_selection(discovery)
                if expectation.require_repository_selection:
                    self.assertIsNotNone(
                        repo_selection,
                        msg=f"{expectation.name}: expected repository selection record",
                    )
                    assert repo_selection is not None
                    self.assertIsNotNone(repo_selection.primary_candidate_id)
                    self.assertGreaterEqual(
                        repo_selection.confidence,
                        expectation.min_repository_selection_confidence,
                    )
                    repo_assets = [
                        asset
                        for asset in discovery.research_assets.assets
                        if asset.asset_type == ResearchAssetType.REPOSITORY and asset.selected_primary
                    ]
                    self.assertTrue(repo_assets, msg=f"{expectation.name}: repository asset not selected")

                self.assertEqual(
                    strategy.strategy.primary_posture,
                    expectation.expected_posture,
                    msg=f"{expectation.name}: unexpected strategy posture",
                )
                self.assertGreaterEqual(
                    len(strategy.resource_bindings.bindings),
                    expectation.min_binding_count,
                )
                self.assertEqual(
                    strategy.reuse_plan.reuse_mode,
                    expectation.expected_reuse_mode,
                )

                if expectation.min_execution_readiness == ReadinessLevel.READY:
                    self.assertEqual(strategy.metadata.status, PlanningStatus.COMPLETE.value)
                    self.assertEqual(strategy.risk_assessment.blocking_risks, [])
                elif expectation.min_execution_readiness == ReadinessLevel.NOT_READY:
                    self.assertTrue(
                        strategy.strategy.primary_posture == StrategyPosture.GREENFIELD
                        or strategy.risk_assessment.blocking_risks
                    )
                else:
                    self.assertIn(
                        strategy.metadata.status,
                        {
                            PlanningStatus.PARTIAL.value,
                            PlanningStatus.COMPLETE.value,
                            PlanningStatus.DEGRADED.value,
                        },
                    )

                if expectation.require_non_greenfield_when_repo and repo_selection:
                    if repo_selection.primary_candidate_id is not None:
                        self.assertNotEqual(
                            strategy.strategy.primary_posture,
                            StrategyPosture.GREENFIELD,
                            msg=f"{expectation.name}: must not commit greenfield when repo selected",
                        )

                if strategy.strategy.primary_posture != StrategyPosture.GREENFIELD:
                    self.assertTrue(
                        strategy.generation_plan.generation_required
                        or len(strategy.resource_bindings.bindings) > 0,
                        msg=f"{expectation.name}: non-greenfield plan must bind resources or authorize generation",
                    )

                if expectation.require_repository_selection:
                    self.assertGreater(len(discovery.research_assets.assets), 0)

                if repo_selection is not None and repo_selection.primary_candidate_id:
                    self.assertGreater(len(repo_selection.confidence_composition.contributions), 0)

                trace = build_planning_decision_trace(discovery, strategy)
                self.assertIn(DecisionStageName.SELECTION, {s.stage for s in trace.stages})
                self.assertIn(DecisionStageName.BINDING, {s.stage for s in trace.stages})

                graph = build_execution_graph(discovery, strategy)
                self.assertGreater(len(graph.nodes), 0)
                if strategy.strategy.primary_posture != StrategyPosture.GREENFIELD:
                    self.assertTrue(any(node.stage_type.value == "clone_repository" for node in graph.nodes))


class DiscoveryPlanningIntegrationTest(unittest.TestCase):
    def test_resnet_embedded_discovery_to_official_repository_strategy(self) -> None:
        from tests.benchmarks.golden.fixtures import resnet_official_analysis

        analysis = resnet_official_analysis()
        discovery = _embedded_discovery_workflow().run(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)

        self.assertGreater(discovery.metadata.selection_count, 0)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)
        self.assertGreater(len(strategy.resource_bindings.bindings), 0)


if __name__ == "__main__":
    unittest.main()
