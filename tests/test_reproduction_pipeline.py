"""Application and facade tests for reproduction pipeline."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from application.platform_execution import MaterializationGateError, PlatformExecutionService
from application.reproduction_pipeline import ReproductionPipelineService
from models.execution_engine import ExecutionRunStatus
from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
from models.execution_materialization import MaterializationReport, MaterializationStatus
from models.paper_reproduction_analysis import (
    AnalysisGoal,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionScope,
)
from models.report import ReportModel
from runtime.context import RuntimeContext
from runtime.resources.manager import RuntimeResourceManager
from runtime.session.materialization_artifacts import MaterializationArtifactStore
from tests.test_execution_materialization_fixtures import materializable_graph, strategy_with_primary_repo


class ReproductionPipelineServiceTest(unittest.TestCase):
    def test_blocked_when_materialization_not_ready(self) -> None:
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="Blocked Paper"),
            goal=AnalysisGoal(scope=ReproductionScope.TRAINING, research_goal="test"),
        )
        from validation.research_resource_discovery import build_research_resource_discovery

        discovery = build_research_resource_discovery(
            {
                "metadata": {
                    "discovery_id": "discovery-1",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "status": "complete",
                },
                "analysis_reference": {
                    "analysis_schema_version": "1.0",
                    "paper_title": "Blocked Paper",
                    "analysis_content_hash": "hash-1",
                },
            }
        )
        strategy = strategy_with_primary_repo()
        graph = materializable_graph()

        platform_execution = MagicMock(spec=PlatformExecutionService)

        def _analyze(_path):
            return analysis

        def _discover(_analysis):
            return discovery

        def _plan(_analysis, _discovery):
            return strategy

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = ReproductionPipelineService(
                analyze=_analyze,
                discover=_discover,
                plan=_plan,
                platform_execution=platform_execution,
                workspace_root=root,
            )
            with unittest.mock.patch(
                "application.reproduction_pipeline.build_execution_graph",
                return_value=graph,
            ), unittest.mock.patch(
                "application.reproduction_pipeline.materialize_execution_graph",
            ) as materialize:
                from models.execution_materialization import ExecutionMaterialization

                materialize.return_value = ExecutionMaterialization(
                    materialization_id="mat-blocked",
                    strategy_id=strategy.metadata.strategy_id,
                    graph_id=graph.graph_id,
                    materialized_graph=graph,
                    report=MaterializationReport(status=MaterializationStatus.BLOCKED),
                    created_at=datetime.now(UTC),
                )
                result = service.reproduce(Path("paper.pdf"))
        self.assertTrue(result.blocked)
        self.assertEqual(result.report.final_status, "blocked")
        platform_execution.run_execution.assert_not_called()


class PlatformExecutionReadyGateTest(unittest.TestCase):
    def test_run_execution_requires_ready_report_even_for_enriched_graph(self) -> None:
        from tests.execution_engine_fixtures import materialized_linear_graph

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context = RuntimeContext(RuntimeResourceManager())
            service = PlatformExecutionService(context, root, engine_factory=lambda: MagicMock())
            with self.assertRaises(MaterializationGateError):
                service.run_execution(materialized_linear_graph())

    def test_run_execution_rejects_non_ready_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context = RuntimeContext(RuntimeResourceManager())
            service = PlatformExecutionService(context, root, engine_factory=lambda: MagicMock())
            graph = ExecutionGraph(
                graph_id="graph-1",
                created_at=datetime.now(UTC),
                strategy_id="strategy-1",
                nodes=[
                    ExecutionGraphNode(
                        node_id="node-1",
                        stage_type=ExecutionGraphStageType.PREPARE_ENVIRONMENT,
                        label="Prepare Environment",
                    )
                ],
            )
            with self.assertRaises(MaterializationGateError):
                service.run_execution(
                    graph,
                    materialization_report=MaterializationReport(
                        status=MaterializationStatus.BLOCKED,
                    ),
                )


if __name__ == "__main__":
    unittest.main()
