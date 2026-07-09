"""Tests for decision trace artifact generation."""

from __future__ import annotations

import unittest

from discovery.decision_trace import build_discovery_decision_trace
from discovery.workflow import DiscoveryWorkflow
from execution_planning.decision_trace import build_planning_decision_trace
from execution_planning.workflow import ExecutionPlanningWorkflow
from models.decision_trace import DecisionStageName
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService
from tests.benchmarks.golden.fixtures import resnet_official_analysis


class DecisionTraceTest(unittest.TestCase):
    def test_discovery_trace_includes_pipeline_stages(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(providers=[EmbeddedResourceProvider()]),
            evidence_service=EvidenceService(providers=[EmbeddedEvidenceProvider()]),
            verification_service=VerificationService(providers=[EmbeddedVerificationProvider()]),
            ranking_service=RankingService(providers=[EmbeddedRankingProvider()]),
        )
        discovery = workflow.run(resnet_official_analysis())
        trace = build_discovery_decision_trace(discovery)
        stages = {record.stage for record in trace.stages}
        self.assertIn(DecisionStageName.REPOSITORY, stages)
        self.assertIn(DecisionStageName.EVIDENCE, stages)
        self.assertIn(DecisionStageName.SELECTION, stages)
        for record in trace.stages:
            self.assertTrue(record.decision_rule)
            self.assertTrue(record.rationale)

    def test_planning_trace_extends_discovery_stages(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(providers=[EmbeddedResourceProvider()]),
            evidence_service=EvidenceService(providers=[EmbeddedEvidenceProvider()]),
            verification_service=VerificationService(providers=[EmbeddedVerificationProvider()]),
            ranking_service=RankingService(providers=[EmbeddedRankingProvider()]),
        )
        analysis = resnet_official_analysis()
        discovery = workflow.run(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        trace = build_planning_decision_trace(discovery, strategy)
        stages = [record.stage for record in trace.stages]
        self.assertEqual(stages[:5], [
            DecisionStageName.REPOSITORY,
            DecisionStageName.EVIDENCE,
            DecisionStageName.VERIFICATION,
            DecisionStageName.RANKING,
            DecisionStageName.SELECTION,
        ])
        self.assertIn(DecisionStageName.BINDING, stages)
        self.assertIn(DecisionStageName.RISK, stages)
        self.assertEqual(trace.strategy_id, strategy.metadata.strategy_id)


if __name__ == "__main__":
    unittest.main()
