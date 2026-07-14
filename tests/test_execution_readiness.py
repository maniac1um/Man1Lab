"""Tests for typed execution evidence and bounded preparation tasks."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from application.platform_execution import PlatformExecutionService
from application.reproduction_pipeline import ReproductionPipelineService
from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.ports.executor import ArtifactCandidate

from discovery.execution_evidence import project_execution_evidence
from execution.preparation.operations import execute_preparation
from models.execution_preparation import PreparationOperation, PreparationRequest
from execution_materialization.materializer import ExecutionMaterializer
from execution_materialization.ports import MaterializationContext
from models.execution_evidence import (
    CheckpointExecutionEvidence,
    ConfigurationExecutionEvidence,
    ConfigurationMode,
    DatasetExecutionEvidence,
    ExecutionEvidenceBundle,
    PreparationSourceKind,
    RepositoryExecutionEvidence,
)
from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
from models.execution_materialization import MaterializationStatus
from models.execution_engine import OutputDeclaration
from models.paper_reproduction_analysis import (
    AnalysisGoal,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionScope,
)
from models.research_resource_discovery import (
    AnalysisReference,
    CandidateResources,
    CandidateStatus,
    CollectionSource,
    CollectionSourceType,
    DiscoveryMetadata,
    DiscoveryProvider,
    DiscoveryStatus,
    EvidenceCollection,
    EvidencePolarity,
    EvidenceRecord,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceType,
    FetchStatus,
    ObservedFact,
    Officiality,
    RepositoryCandidate,
    ResearchResourceDiscovery,
    ResourceIdentity,
    ResourceType,
)
from runtime.session.execution_evidence_artifacts import ExecutionEvidenceArtifactStore
from runtime.context import RuntimeContext
from tests.test_execution_materialization_fixtures import strategy_with_primary_repo


class ExecutionEvidenceProjectionTest(unittest.TestCase):
    def test_projects_repository_execution_facts_and_round_trips(self) -> None:
        discovery = _repository_discovery()
        bundle = project_execution_evidence(
            discovery,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        self.assertEqual(len(bundle.repositories), 1)
        repository = bundle.repositories[0]
        self.assertEqual(repository.source_kind, PreparationSourceKind.WORKSPACE)
        self.assertEqual(repository.target_path, "repositories/demo")
        self.assertEqual(repository.entry_script, "train.py")
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ExecutionEvidenceArtifactStore(Path(temp_dir))
            store.save(bundle)
            self.assertEqual(store.load(), bundle)

    def test_embedded_uri_credentials_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RepositoryExecutionEvidence(
                candidate_id="repo",
                source_kind=PreparationSourceKind.GIT,
                source_uri="https://token@example.com/repo.git",
                revision="abc",
                target_path="repositories/repo",
            )


class PreparationOperationTest(unittest.TestCase):
    def test_request_rejects_workspace_escape(self) -> None:
        with self.assertRaises(ValueError):
            PreparationRequest(
                operation=PreparationOperation.DATASET,
                source_kind="workspace",
                target_path="../outside",
                receipt_path="receipt.json",
            )
    def test_repository_verification_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repositories" / "demo"
            repo.mkdir(parents=True)
            (repo / "train.py").write_text("print('ok')\n", encoding="utf-8")
            request = PreparationRequest(
                operation=PreparationOperation.REPOSITORY,
                source_kind="workspace",
                target_path="repositories/demo",
                receipt_path=".man1lab/preparation/repo/receipt.json",
                required_paths=("train.py",),
            )
            receipt = execute_preparation(request, workspace_root=root)
            self.assertTrue(receipt.is_file())
            self.assertIn('"operation": "repository"', receipt.read_text(encoding="utf-8"))

    def test_local_checkpoint_checksum_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            checkpoint = root / "checkpoints" / "model.bin"
            checkpoint.parent.mkdir()
            checkpoint.write_bytes(b"weights")
            expected = hashlib.sha256(b"weights").hexdigest()
            request = PreparationRequest(
                operation=PreparationOperation.CHECKPOINT,
                source_kind="workspace",
                target_path="checkpoints/model.bin",
                receipt_path=".man1lab/preparation/checkpoint/receipt.json",
                checksum_sha256=expected,
            )
            receipt = execute_preparation(request, workspace_root=root)
            self.assertIn(expected, receipt.read_text(encoding="utf-8"))

    def test_deterministic_configuration_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = PreparationRequest(
                operation=PreparationOperation.CONFIGURATION,
                source_kind="deterministic_render",
                target_path="configs/reproduce.json",
                receipt_path=".man1lab/preparation/config/receipt.json",
                configuration_values={"epochs": 1, "seed": 7},
            )
            execute_preparation(request, workspace_root=root)
            self.assertEqual(
                (root / "configs" / "reproduce.json").read_text(encoding="utf-8"),
                '{\n  "epochs": 1,\n  "seed": 7\n}\n',
            )

    def test_receipt_resume_validation_checks_prepared_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "datasets" / "data.bin"
            target.parent.mkdir()
            target.write_bytes(b"dataset")
            request = PreparationRequest(
                operation=PreparationOperation.DATASET,
                source_kind="workspace",
                target_path="datasets/data.bin",
                receipt_path=".man1lab/preparation/dataset/dataset_receipt.json",
            )
            receipt = execute_preparation(request, workspace_root=root)
            tracker = InMemoryArtifactTracker(workspace_root=root.as_posix())
            artifact = tracker.register_candidate(
                run_id="run-1",
                task_id="task-1",
                attempt_id="attempt-1",
                candidate=ArtifactCandidate(
                    logical_name="dataset",
                    artifact_type="dataset",
                    location_ref=receipt.as_posix(),
                    size_bytes=receipt.stat().st_size,
                ),
            )
            tracker.validate_required_outputs(
                run_id="run-1",
                task_id="task-1",
                attempt_id="attempt-1",
                declarations=(OutputDeclaration(logical_name="dataset", artifact_type="dataset"),),
            )
            self.assertTrue(tracker.artifact_still_valid(artifact.artifact_id))
            target.unlink()
            self.assertFalse(tracker.artifact_still_valid(artifact.artifact_id))


class FullGraphMaterializationTest(unittest.TestCase):
    def test_all_preparation_stage_types_have_specs(self) -> None:
        discovery = _repository_discovery()
        base = project_execution_evidence(discovery)
        bundle = base.model_copy(
            update={
                "datasets": (
                    DatasetExecutionEvidence(
                        candidate_id="candidate-dataset",
                        source_kind=PreparationSourceKind.HTTPS,
                        source_uri="https://example.com/data.zip",
                        target_path="datasets/demo",
                        checksum_sha256="a" * 64,
                        archive_format="zip",
                    ),
                ),
                "checkpoints": (
                    CheckpointExecutionEvidence(
                        candidate_id="candidate-checkpoint",
                        source_kind=PreparationSourceKind.WORKSPACE,
                        target_path="checkpoints/model.bin",
                    ),
                ),
                "configurations": (
                    ConfigurationExecutionEvidence(
                        candidate_id="candidate-config",
                        mode=ConfigurationMode.DETERMINISTIC_RENDER,
                        target_path="configs/reproduce.json",
                        values={"seed": 7},
                    ),
                ),
            }
        )
        stages = (
            (ExecutionGraphStageType.CLONE_REPOSITORY, "candidate-repo-1"),
            (ExecutionGraphStageType.DOWNLOAD_DATASET, "candidate-dataset"),
            (ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS, "candidate-checkpoint"),
            (ExecutionGraphStageType.GENERATE_CONFIG, "candidate-config"),
        )
        nodes = [
            ExecutionGraphNode(
                node_id=f"node-{stage.value}",
                stage_type=stage,
                label=stage.value,
                asset_ids=[candidate_id],
                depends_on=[f"node-{stages[index - 1][0].value}"] if index else [],
            )
            for index, (stage, candidate_id) in enumerate(stages)
        ]
        graph = ExecutionGraph(
            graph_id="graph-all-preparation",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            strategy_id="strategy-1",
            nodes=nodes,
        )
        result = ExecutionMaterializer().materialize(
            strategy_with_primary_repo(),
            discovery,
            graph,
            MaterializationContext(workspace_root="workspace"),
            evidence_bundle=bundle,
        )
        self.assertEqual(result.report.status, MaterializationStatus.READY)
        self.assertTrue(all(node.execution_spec is not None for node in result.materialized_graph.nodes))

    def test_prepared_repository_graph_becomes_ready(self) -> None:
        discovery = _repository_discovery()
        bundle = project_execution_evidence(
            discovery,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        graph = _repository_graph(repository_dependency=True)
        result = ExecutionMaterializer().materialize(
            strategy_with_primary_repo(),
            discovery,
            graph,
            MaterializationContext(workspace_root="workspace"),
            evidence_bundle=bundle,
        )
        self.assertEqual(result.report.status, MaterializationStatus.READY)
        repository = result.materialized_graph.nodes[0].execution_spec
        assert repository is not None
        self.assertEqual(repository.template_id, "local/prepare_repository")
        self.assertEqual(set(repository.artifact_paths), {"repository"})

    def test_future_repository_reference_requires_dependency(self) -> None:
        discovery = _repository_discovery()
        bundle = project_execution_evidence(discovery)
        result = ExecutionMaterializer().materialize(
            strategy_with_primary_repo(),
            discovery,
            _repository_graph(repository_dependency=False),
            MaterializationContext(workspace_root="workspace"),
            evidence_bundle=bundle,
        )
        self.assertEqual(result.report.status, MaterializationStatus.BLOCKED)
        self.assertTrue(
            any(issue.code == "future_reference_without_producer_dependency" for issue in result.report.errors)
        )

    def test_controlled_prepared_repository_executes_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repositories" / "demo"
            repo.mkdir(parents=True)
            for name in ("train.py", "eval.py"):
                (repo / name).write_text("print('unused')\n", encoding="utf-8")
            (repo / "requirements.txt").write_text("", encoding="utf-8")
            (repo / "config.json").write_text("{}\n", encoding="utf-8")
            (repo / "compare.py").write_text(
                "from pathlib import Path\n"
                "import argparse\n"
                "p=argparse.ArgumentParser()\n"
                "p.add_argument('--output', required=True)\n"
                "a=p.parse_args()\n"
                "o=Path(a.output)\n"
                "o.parent.mkdir(parents=True, exist_ok=True)\n"
                "o.write_text('result', encoding='utf-8')\n",
                encoding="utf-8",
            )
            discovery = _repository_discovery()
            bundle = project_execution_evidence(discovery)
            graph = ExecutionGraph(
                graph_id="graph-controlled-e2e",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                strategy_id="strategy-1",
                nodes=[
                    ExecutionGraphNode(
                        node_id="node-clone-repository",
                        stage_type=ExecutionGraphStageType.CLONE_REPOSITORY,
                        label="Prepare Repository",
                        binding_ids=["binding-primary-repository"],
                    ),
                    ExecutionGraphNode(
                        node_id="node-comparison",
                        stage_type=ExecutionGraphStageType.COMPARISON,
                        label="Comparison",
                        depends_on=["node-clone-repository"],
                    ),
                ],
            )
            materialization = ExecutionMaterializer().materialize(
                strategy_with_primary_repo(),
                discovery,
                graph,
                MaterializationContext(workspace_root=root.as_posix()),
                evidence_bundle=bundle,
            )
            self.assertEqual(materialization.report.status, MaterializationStatus.READY)
            service = PlatformExecutionService(RuntimeContext.create(), root)
            outcome = service.run_execution(
                materialization.materialized_graph,
                materialization_report=materialization.report,
                resume=False,
            )
            self.assertEqual(
                outcome.status.value,
                "success",
                outcome.report.model_dump() if outcome.report is not None else None,
            )
            self.assertTrue((repo / "outputs" / "result.json").is_file())
            self.assertTrue(
                (root / ".man1lab" / "preparation" / "node-clone-repository" / "repository_receipt.json").is_file()
            )

    def test_controlled_one_command_pipeline_reaches_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repositories" / "demo"
            repo.mkdir(parents=True)
            (repo / "requirements.txt").write_text("", encoding="utf-8")
            (repo / "config.json").write_text("{}\n", encoding="utf-8")
            workload = (
                "from pathlib import Path\n"
                "Path('outputs').mkdir(exist_ok=True)\n"
                "Path('outputs/result.json').write_text('result', encoding='utf-8')\n"
            )
            (repo / "train.py").write_text(workload, encoding="utf-8")
            (repo / "eval.py").write_text(workload, encoding="utf-8")
            (repo / "compare.py").write_text(
                "from pathlib import Path\n"
                "import argparse\n"
                "p=argparse.ArgumentParser()\n"
                "p.add_argument('--output', required=True)\n"
                "a=p.parse_args()\n"
                "o=Path(a.output)\n"
                "o.parent.mkdir(parents=True, exist_ok=True)\n"
                "o.write_text('report', encoding='utf-8')\n",
                encoding="utf-8",
            )
            analysis = PaperReproductionAnalysis(
                metadata=PaperMetadata(title="Controlled Paper"),
                goal=AnalysisGoal(
                    scope=ReproductionScope.TRAINING,
                    research_goal="Controlled reproduction",
                ),
            )
            discovery = _repository_discovery()
            strategy = strategy_with_primary_repo()
            service = ReproductionPipelineService(
                analyze=lambda _path: analysis,
                discover=lambda _analysis: discovery,
                plan=lambda _analysis, _discovery: strategy,
                platform_execution=PlatformExecutionService(RuntimeContext.create(), root),
                workspace_root=root,
                persist_planning_artifacts=False,
            )
            result = service.reproduce(root / "paper.pdf")
            self.assertFalse(result.blocked, result.diagnostics)
            self.assertIsNotNone(result.execution)
            assert result.execution is not None
            self.assertEqual(result.execution.status.value, "success")
            self.assertEqual(result.report.final_status, "success")


def _repository_discovery() -> ResearchResourceDiscovery:
    candidate_id = "candidate-repo-1"
    candidate = RepositoryCandidate(
        candidate_id=candidate_id,
        identity=ResourceIdentity(
            provider=DiscoveryProvider.GITHUB,
            normalized_url="https://github.com/example/demo.git",
        ),
        provider=DiscoveryProvider.GITHUB,
        resource_type=ResourceType.OFFICIAL_REPOSITORY,
        url="https://github.com/example/demo.git",
        officiality=Officiality.OFFICIAL,
        collection_source=CollectionSource(source_type=CollectionSourceType.MANUAL),
        status=CandidateStatus.VERIFIED,
    )
    record = EvidenceRecord(
        evidence_id="evidence-repository-execution",
        candidate_id=candidate_id,
        evidence_type=EvidenceType.FILE_PRESENCE,
        evidence_source=EvidenceSource(
            source_kind=EvidenceSourceKind.PAPER_TEXT,
            fetch_status=FetchStatus.SUCCESS,
        ),
        observed_fact=ObservedFact(
            extensions={
                "prepared_repo_path": "repositories/demo",
                "requirements_file": "requirements.txt",
                "entry_script": "train.py",
                "eval_script": "eval.py",
                "comparison_script": "compare.py",
                "config_path": "config.json",
                "output_path": "outputs/result.json",
            }
        ),
        polarity=EvidencePolarity.SUPPORTS,
        confidence=1.0,
    )
    return ResearchResourceDiscovery(
        metadata=DiscoveryMetadata(
            discovery_id="discovery-1",
            status=DiscoveryStatus.COMPLETE,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        analysis_reference=AnalysisReference(
            analysis_schema_version="1.0",
            paper_title="Test",
            analysis_content_hash="hash-1",
        ),
        candidate_resources=CandidateResources(candidates=[candidate]),
        evidence=EvidenceCollection(records=[record]),
    )


def _repository_graph(*, repository_dependency: bool) -> ExecutionGraph:
    repository_id = "node-clone-repository"
    nodes = [
        ExecutionGraphNode(
            node_id=repository_id,
            stage_type=ExecutionGraphStageType.CLONE_REPOSITORY,
            label="Prepare Repository",
            binding_ids=["binding-primary-repository"],
        ),
        ExecutionGraphNode(
            node_id="node-prepare-environment",
            stage_type=ExecutionGraphStageType.PREPARE_ENVIRONMENT,
            label="Prepare Environment",
            depends_on=[repository_id] if repository_dependency else [],
            binding_ids=["binding-primary-repository"],
        ),
        ExecutionGraphNode(
            node_id="node-training",
            stage_type=ExecutionGraphStageType.TRAINING,
            label="Training",
            depends_on=["node-prepare-environment"],
            binding_ids=["binding-primary-repository"],
        ),
        ExecutionGraphNode(
            node_id="node-evaluation",
            stage_type=ExecutionGraphStageType.EVALUATION,
            label="Evaluation",
            depends_on=["node-training"],
        ),
        ExecutionGraphNode(
            node_id="node-comparison",
            stage_type=ExecutionGraphStageType.COMPARISON,
            label="Comparison",
            depends_on=["node-evaluation"],
        ),
    ]
    return ExecutionGraph(
        graph_id="graph-readiness",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        strategy_id="strategy-1",
        nodes=nodes,
    )


if __name__ == "__main__":
    unittest.main()
