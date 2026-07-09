"""Tests for execution graph generation."""

from __future__ import annotations

import unittest

from discovery.workflow import DiscoveryWorkflow
from execution_planning.execution_graph import build_execution_graph
from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution_graph import ExecutionGraphStageType
from models.execution_strategy import StrategyPosture
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService
from tests.benchmarks.golden.fixtures import greenfield_no_resources_analysis, resnet_official_analysis


class ExecutionGraphTest(unittest.TestCase):
    def test_official_repository_graph_includes_clone_and_training(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(providers=[EmbeddedResourceProvider()]),
            evidence_service=EvidenceService(providers=[EmbeddedEvidenceProvider()]),
            verification_service=VerificationService(providers=[EmbeddedVerificationProvider()]),
            ranking_service=RankingService(providers=[EmbeddedRankingProvider()]),
        )
        analysis = resnet_official_analysis()
        discovery = workflow.run(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        graph = build_execution_graph(discovery, strategy)
        stage_types = {node.stage_type for node in graph.nodes}
        self.assertIn(ExecutionGraphStageType.CLONE_REPOSITORY, stage_types)
        self.assertIn(ExecutionGraphStageType.TRAINING, stage_types)
        self.assertIn(ExecutionGraphStageType.EVALUATION, stage_types)
        self.assertIn(ExecutionGraphStageType.COMPARISON, stage_types)
        self.assertEqual(graph.strategy_id, strategy.metadata.strategy_id)

    def test_greenfield_graph_skips_clone(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(providers=[EmbeddedResourceProvider()]),
            evidence_service=EvidenceService(providers=[EmbeddedEvidenceProvider()]),
            verification_service=VerificationService(providers=[EmbeddedVerificationProvider()]),
            ranking_service=RankingService(providers=[EmbeddedRankingProvider()]),
        )
        analysis = greenfield_no_resources_analysis()
        discovery = workflow.run(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.GREENFIELD)
        graph = build_execution_graph(discovery, strategy)
        stage_types = {node.stage_type for node in graph.nodes}
        self.assertNotIn(ExecutionGraphStageType.CLONE_REPOSITORY, stage_types)
        self.assertIn(ExecutionGraphStageType.PREPARE_ENVIRONMENT, stage_types)


if __name__ == "__main__":
    unittest.main()
