"""Tests for runtime workspace persistence and resume utilities."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from models.execution_strategy import (
    AnalysisReference,
    DiscoveryReference,
    ExecutionStrategy,
    InputReferences,
    PlanningStatus,
    Strategy,
    StrategyMetadata,
    StrategyPosture,
)
from models.paper_reproduction_analysis import (
    AnalysisGoal,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionScope,
)
from models.research_resource_discovery import (
    AnalysisReference as DiscoveryAnalysisReference,
    DiscoveryMetadata,
    DiscoveryStatus,
    ResearchResourceDiscovery,
)
from runtime.session.workspace import SessionWorkspace
from runtime.session.workspace_resume import (
    WorkspaceArtifactStatus,
    artifact_status,
    diagnose_for_discover,
    diagnose_for_plan,
    hydrate_workspace_from_disk,
)
from runtime.session.workspace_store import WorkspaceArtifactStore
from validation.execution_strategy import build_execution_strategy
from validation.research_resource_discovery import build_research_resource_discovery
from tests.test_execution_strategy_validation import _minimal_payload


def _sample_analysis(source: Path | None = None) -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(title="Test Paper", source_path=source),
        goal=AnalysisGoal(
            scope=ReproductionScope.TRAINING,
            research_goal="Reproduce the benchmark.",
        ),
    )


def _sample_discovery() -> ResearchResourceDiscovery:
    return build_research_resource_discovery(
        {
            "metadata": {
                "discovery_id": "disc-1",
                "created_at": "2026-07-02T00:00:00+00:00",
                "status": "complete",
                "candidate_count": 0,
                "selection_count": 0,
                "unresolved_gap_count": 0,
            },
            "analysis_reference": {
                "analysis_schema_version": "1.0",
                "paper_title": "Test Paper",
                "analysis_content_hash": "hash",
            },
        }
    )


def _sample_strategy() -> ExecutionStrategy:
    now = datetime.now(UTC)
    return ExecutionStrategy(
        metadata=StrategyMetadata(
            strategy_id="strategy-1",
            created_at=now,
            status=PlanningStatus.COMPLETE,
        ),
        input_references=InputReferences(
            analysis_reference=AnalysisReference(
                analysis_schema_version="1.0",
                paper_title="Test Paper",
                analysis_content_hash="analysis-hash",
            ),
            discovery_reference=DiscoveryReference(
                discovery_schema_version="1.0",
                discovery_id="disc-1",
                discovery_content_hash="discovery-hash",
                discovery_status=DiscoveryStatus.COMPLETE,
            ),
        ),
        strategy=Strategy(
            primary_posture=StrategyPosture.GREENFIELD,
            rationale="Test strategy.",
        ),
    )


class WorkspaceArtifactStoreTest(unittest.TestCase):
    def test_persists_analysis_discovery_and_strategy_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = WorkspaceArtifactStore(root)
            paper = root / "paper.pdf"
            analysis = _sample_analysis(paper)
            discovery = _sample_discovery()
            strategy = _sample_strategy()

            store.save_analysis(analysis)
            store.save_discovery(discovery)
            store.save_strategy(strategy)

            self.assertTrue((root / "analysis" / "analysis.json").is_file())
            self.assertTrue((root / "analysis" / "analysis.md").is_file())
            self.assertTrue((root / "discovery" / "resources.json").is_file())
            self.assertTrue((root / "discovery" / "summary.md").is_file())
            self.assertTrue((root / "planning" / "execution_strategy.json").is_file())
            self.assertTrue((root / "planning" / "summary.md").is_file())

            restored_analysis = store.load_analysis()
            restored_discovery = store.load_discovery()
            restored_strategy = store.load_strategy()

            self.assertIsNotNone(restored_analysis)
            self.assertIsNotNone(restored_discovery)
            self.assertIsNotNone(restored_strategy)
            assert restored_analysis is not None
            assert restored_discovery is not None
            assert restored_strategy is not None
            self.assertEqual(restored_analysis.metadata.title, "Test Paper")
            self.assertEqual(restored_discovery.metadata.discovery_id, "disc-1")
            self.assertEqual(restored_strategy.metadata.strategy_id, "strategy-1")

    def test_persists_decision_trace_and_execution_graph(self) -> None:
        from datetime import UTC, datetime

        from models.decision_trace import DecisionStageName, DecisionStageRecord, DecisionTrace
        from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = WorkspaceArtifactStore(root)
            trace = DecisionTrace(
                trace_id="trace-1",
                created_at=datetime.now(UTC),
                stages=[
                    DecisionStageRecord(
                        stage=DecisionStageName.SELECTION,
                        decision_rule="selection:test",
                        rationale="Test selection.",
                    )
                ],
            )
            graph = ExecutionGraph(
                graph_id="graph-1",
                created_at=datetime.now(UTC),
                strategy_id="strategy-1",
                nodes=[
                    ExecutionGraphNode(
                        node_id="node-1",
                        stage_type=ExecutionGraphStageType.CLONE_REPOSITORY,
                        label="Clone Repository",
                    )
                ],
            )
            store.save_decision_trace(trace)
            store.save_execution_graph(graph)

            self.assertTrue((root / "decision" / "decision_trace.json").is_file())
            self.assertTrue((root / "decision" / "decision_trace.md").is_file())
            self.assertTrue((root / "decision" / "execution_graph.json").is_file())
            self.assertTrue((root / "decision" / "execution_graph.md").is_file())
            self.assertIsNotNone(store.load_decision_trace())
            self.assertIsNotNone(store.load_execution_graph())

    def test_round_trip_strategy_via_builder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = WorkspaceArtifactStore(Path(temp_dir))
            strategy = build_execution_strategy(_minimal_payload())
            store.save_strategy(strategy)
            restored = store.load_strategy()
            self.assertIsNotNone(restored)
            assert restored is not None
            self.assertEqual(
                restored.model_dump(mode="json"),
                strategy.model_dump(mode="json"),
            )

    def test_parsed_document_cache_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper = root / "paper.pdf"
            paper.write_bytes(b"%PDF-1.4 cached")
            store = WorkspaceArtifactStore(root)
            store.save_parsed_document(paper, "# Parsed markdown")
            restored = store.load_parsed_document(paper)
            self.assertEqual(restored, "# Parsed markdown")
            self.assertTrue(store.has_parsed_document())

    def test_parsed_document_cache_invalidates_on_mtime_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper = root / "paper.pdf"
            paper.write_bytes(b"%PDF-1.4 cached")
            store = WorkspaceArtifactStore(root)
            store.save_parsed_document(paper, "# Parsed markdown")
            paper.write_bytes(b"%PDF-1.4 changed")
            self.assertIsNone(store.load_parsed_document(paper))


class WorkspaceResumeTest(unittest.TestCase):
    def test_artifact_status_reports_missing_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            status = artifact_status(root)
            self.assertEqual(status, WorkspaceArtifactStatus(False, False, False))

            store = WorkspaceArtifactStore(root)
            store.save_analysis(_sample_analysis())
            status = artifact_status(root)
            self.assertEqual(status.analysis, True)
            self.assertFalse(status.discovery)

    def test_hydrate_workspace_from_disk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = WorkspaceArtifactStore(root)
            analysis = _sample_analysis(root / "paper.pdf")
            store.save_analysis(analysis)
            store.save_discovery(_sample_discovery())

            workspace = SessionWorkspace(workspace_root=root)
            hydrate_workspace_from_disk(workspace)

            self.assertIsNotNone(workspace.current_analysis)
            self.assertIsNotNone(workspace.current_discovery)
            self.assertEqual(workspace.current_paper, root / "paper.pdf")

    def test_diagnose_for_discover_recommends_analyze(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            diagnostic = diagnose_for_discover(Path(temp_dir))
            self.assertIsNotNone(diagnostic)
            assert diagnostic is not None
            self.assertEqual(diagnostic.recommended_command, "analyze <paper.pdf>")
            self.assertIn("analysis", diagnostic.missing)

    def test_diagnose_for_plan_recommends_discover_when_analysis_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            WorkspaceArtifactStore(root).save_analysis(_sample_analysis())
            diagnostic = diagnose_for_plan(root)
            self.assertIsNotNone(diagnostic)
            assert diagnostic is not None
            self.assertEqual(diagnostic.recommended_command, "discover")
            self.assertEqual(diagnostic.missing, ("discovery",))


if __name__ == "__main__":
    unittest.main()
