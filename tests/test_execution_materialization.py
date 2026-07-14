"""Tests for materializer determinism, security, and integration."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from execution.decomposition import decompose_execution_graph
from execution.backends.local_executor import parse_local_invocation
from execution_materialization.materializer import ExecutionMaterializer
from execution_materialization.ports import MaterializationContext
from execution_materialization.resolvers.workspace import _normalize_relative
from execution_materialization.task_factory import project_spec_to_metadata
from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
from models.execution_materialization import MaterializationStatus
from models.research_resource_discovery import (
    AnalysisReference,
    DiscoveryMetadata,
    DiscoveryProvenance,
    DiscoveryStatus,
    EvidenceCollection,
    EvidencePolarity,
    EvidenceRecord,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceType,
    FetchStatus,
    ObservedFact,
    ResearchResourceDiscovery,
    ResearchAssetCollection,
)
from tests.test_execution_materialization_fixtures import (
    materializable_graph,
    strategy_with_primary_repo,
)


class MaterializerDeterminismTest(unittest.TestCase):
    def test_materialization_id_is_deterministic(self) -> None:
        materializer = ExecutionMaterializer()
        discovery = _discovery_with_evidence()
        strategy = strategy_with_primary_repo()
        graph = materializable_graph()
        context = MaterializationContext(workspace_root="/tmp/workspace")
        first = materializer.materialize(strategy, discovery, graph, context)
        second = materializer.materialize(strategy, discovery, graph, context)
        self.assertEqual(first.materialization_id, second.materialization_id)

    def test_ready_materialization_for_supported_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repositories" / "demo"
            repo.mkdir(parents=True)
            (repo / "requirements.txt").write_text("pytest\n", encoding="utf-8")
            (repo / "train.py").write_text("print('train')\n", encoding="utf-8")
            (repo / "eval.py").write_text("print('eval')\n", encoding="utf-8")
            (repo / "config.yaml").write_text("x: 1\n", encoding="utf-8")

            discovery = _discovery_with_evidence(prepared_repo_path="repositories/demo")
            strategy = strategy_with_primary_repo()
            graph = materializable_graph()
            context = MaterializationContext(workspace_root=root.as_posix())
            result = ExecutionMaterializer().materialize(strategy, discovery, graph, context)
            self.assertEqual(result.report.status, MaterializationStatus.READY)
            self.assertTrue(all(node.execution_spec is not None for node in result.materialized_graph.nodes))
            training = next(
                node for node in result.materialized_graph.nodes
                if node.stage_type is ExecutionGraphStageType.TRAINING
            )
            comparison = next(
                node for node in result.materialized_graph.nodes
                if node.stage_type is ExecutionGraphStageType.COMPARISON
            )
            assert training.execution_spec is not None
            assert comparison.execution_spec is not None
            self.assertEqual(training.execution_spec.command[1], "train.py")
            self.assertEqual(comparison.execution_spec.command[1], "compare.py")
            self.assertNotIn("placeholder", " ".join(comparison.execution_spec.command))


class MaterializerSecurityTest(unittest.TestCase):
    def test_normalize_relative_rejects_traversal(self) -> None:
        with self.assertRaises(ValueError):
            _normalize_relative("../outside")


class DecompositionProjectionTest(unittest.TestCase):
    def test_execution_spec_projects_to_local_executor_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repositories" / "demo"
            repo.mkdir(parents=True)
            (repo / "train.py").write_text("print('ok')\n", encoding="utf-8")
            discovery = _discovery_with_evidence(
                prepared_repo_path="repositories/demo",
                entry_script="train.py",
                config_path="config.yaml",
                output_path="outputs/out.txt",
            )
            strategy = strategy_with_primary_repo()
            graph = ExecutionGraph(
                graph_id="graph-proj",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                strategy_id=strategy.metadata.strategy_id,
                nodes=[
                    ExecutionGraphNode(
                        node_id="node-training",
                        stage_type=ExecutionGraphStageType.TRAINING,
                        label="Training",
                        binding_ids=["binding-primary-repository"],
                    )
                ],
            )
            materialized = ExecutionMaterializer().materialize(
                strategy,
                discovery,
                graph,
                MaterializationContext(workspace_root=root.as_posix()),
            ).materialized_graph
            result = decompose_execution_graph(materialized, run_id="run-proj")
            task = result.tasks[0]
            spec = materialized.nodes[0].execution_spec
            assert spec is not None
            self.assertEqual(project_spec_to_metadata(spec), {
                key: task.metadata[key]
                for key in project_spec_to_metadata(spec)
            })
            parse_local_invocation(task, default_working_directory=root)
            self.assertTrue(all(not item.required for item in task.inputs))


def _discovery_with_evidence(
    *,
    prepared_repo_path: str = "repositories/demo",
    requirements_file: str = "requirements.txt",
    entry_script: str = "train.py",
    eval_script: str = "eval.py",
    config_path: str = "config.yaml",
    output_path: str = "outputs/out.txt",
    comparison_script: str = "compare.py",
) -> ResearchResourceDiscovery:
    candidate_id = "candidate-repo-1"
    evidence = EvidenceRecord(
        evidence_id="evidence-1",
        candidate_id=candidate_id,
        evidence_type=EvidenceType.FILE_PRESENCE,
        evidence_source=EvidenceSource(
            source_kind=EvidenceSourceKind.PAPER_TEXT,
            provider_name="test",
            fetch_status=FetchStatus.SUCCESS,
        ),
        observed_fact=ObservedFact(
            extensions={
                "prepared_repo_path": prepared_repo_path,
                "requirements_file": requirements_file,
                "entry_script": entry_script,
                "eval_script": eval_script,
                "config_path": config_path,
                "output_path": output_path,
                "comparison_script": comparison_script,
            }
        ),
        polarity=EvidencePolarity.SUPPORTS,
    )
    return ResearchResourceDiscovery(
        metadata=DiscoveryMetadata(
            discovery_id="discovery-1",
            status=DiscoveryStatus.COMPLETE,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        provenance=DiscoveryProvenance(),
        analysis_reference=AnalysisReference(
            analysis_schema_version="1.0",
            paper_title="Test",
            analysis_content_hash="hash-1",
        ),
        evidence=EvidenceCollection(records=[evidence]),
        research_assets=ResearchAssetCollection(),
    )


if __name__ == "__main__":
    unittest.main()
