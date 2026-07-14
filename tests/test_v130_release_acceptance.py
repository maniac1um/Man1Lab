"""Offline, provider-driven v1.3.0 release acceptance for the DeiT case."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from application.platform_execution import PlatformExecutionService
from application.reproduction_pipeline import ReproductionPipelineService
from application.runtime.execution_wiring import (
    bind_workspace_execution_store,
    create_local_executor,
    create_runtime_durable_engine,
)
from discovery.workflow import DiscoveryWorkflow
from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.ports.executor import ExecutorPort, TaskAttemptRequest, TaskAttemptOutcome
from models.execution_engine import ExecutionRunStatus, TraceEventType
from models.execution_strategy import (
    BindingRole,
    ResourceBinding,
    ResourceBindings,
    StrategyPosture,
)
from models.paper_reproduction_analysis import (
    AnalysisGoal,
    AnalysisResources,
    ArtifactReference,
    ArtifactType,
    DatasetResource,
    ExternalResource,
    GapCategory,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionGap,
    ReproductionScope,
)
from models.research_resource_discovery import (
    EvidencePolarity,
    EvidenceRecord,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceType,
    FetchStatus,
    ObservedFact,
    ProviderInvocationStatus,
    ProviderRecord,
    ResourceType,
)
from ports.evidence_provider import EvidenceProviderResult
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from runtime.context import RuntimeContext
from runtime.session.execution_evidence_artifacts import ExecutionEvidenceArtifactStore
from runtime.session.materialization_artifacts import MaterializationArtifactStore
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService
from tests.fixtures import create_sample_paper_pdf
from tests.test_execution_materialization_fixtures import strategy_with_primary_repo


DEIT_REPOSITORY_URL = "https://github.com/facebookresearch/deit"
DEIT_PINNED_COMMIT = "7e160fe43f0252d17191b71cbb5826254114ea5b"
DEIT_DATASET_URL = "https://www.image-net.org/"
DEIT_CHECKPOINT_URL = (
    "https://dl.fbaipublicfiles.com/deit/deit_tiny_patch16_224-a1311bcf.pth"
)


class DeiTReleaseEvidenceProvider:
    """Case-scoped provider fixture for the documented DeiT release acceptance."""

    def collect(self, analysis, collection_result, candidates) -> EvidenceProviderResult:
        del analysis, collection_result
        records: list[EvidenceRecord] = []
        for candidate in candidates:
            facts: dict[str, str]
            if candidate.resource_type is ResourceType.OFFICIAL_REPOSITORY:
                facts = {
                    "source_uri": DEIT_REPOSITORY_URL,
                    "commit_sha": DEIT_PINNED_COMMIT,
                    "prepared_repo_path": "repositories/deit",
                    "manifest_paths": "main.py,requirements.txt,configs/release.json,compare.py",
                    "entry_script": "main.py",
                    "eval_script": "main.py",
                    "comparison_script": "compare.py",
                    "requirements_file": "requirements.txt",
                    "config_path": "configs/release.json",
                    "output_path": "outputs/result.json",
                    "working_directory": "repositories/deit",
                }
            elif candidate.resource_type is ResourceType.DATASET_PORTAL:
                facts = {
                    "source_uri": DEIT_DATASET_URL,
                    "dataset_path": "datasets/imagenet-release-sample",
                }
            elif candidate.resource_type is ResourceType.CHECKPOINT:
                facts = {
                    "source_uri": DEIT_CHECKPOINT_URL,
                    "checkpoint_path": "checkpoints/deit-tiny-release.pth",
                    "checkpoint_format": "pth",
                }
            else:
                continue
            records.append(
                EvidenceRecord(
                    evidence_id=f"release-execution-{candidate.candidate_id}",
                    candidate_id=candidate.candidate_id,
                    evidence_type=EvidenceType.FILE_PRESENCE,
                    evidence_source=EvidenceSource(
                        source_kind=EvidenceSourceKind.PROVIDER_API,
                        provider_name="deit_release_acceptance",
                        uri=candidate.url,
                        fetch_status=FetchStatus.SUCCESS,
                    ),
                    observed_fact=ObservedFact(extensions=facts),
                    polarity=EvidencePolarity.SUPPORTS,
                    confidence=1.0,
                    collected_at=datetime.now(UTC),
                )
            )
        return EvidenceProviderResult(
            evidence_records=records,
            provider_outcomes=[
                ProviderRecord(
                    provider_name="deit_release_acceptance",
                    provider_version="1.0.0",
                    invoked_at=datetime.now(UTC),
                    status=ProviderInvocationStatus.SUCCESS,
                    evidence_contributed=len(records),
                )
            ],
        )


class ExitAfterFirstAttemptExecutor:
    """Test-only process interruption after one task has durably completed."""

    backend_kind = "local"

    def __init__(self, delegate: ExecutorPort) -> None:
        self._delegate = delegate
        self._attempts = 0

    def execute_attempt(self, request: TaskAttemptRequest) -> TaskAttemptOutcome:
        self._attempts += 1
        if self._attempts == 2:
            os._exit(86)
        return self._delegate.execute_attempt(request)


def _analysis(paper_path: Path) -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(
            title="Training data-efficient image transformers & distillation through attention",
            arxiv_id="2012.12877",
            source_path=paper_path,
        ),
        goal=AnalysisGoal(
            scope=ReproductionScope.TRAINING,
            research_goal="Run the bounded DeiT v1.3 release acceptance workflow.",
        ),
        resources=AnalysisResources(
            external_resources=[
                ExternalResource(
                    resource_type="official_repository",
                    name="Official DeiT repository",
                    url=DEIT_REPOSITORY_URL,
                )
            ],
            datasets=[
                DatasetResource(name="ImageNet release sample", link=DEIT_DATASET_URL)
            ],
            artifacts=[
                ArtifactReference(
                    artifact_type=ArtifactType.CHECKPOINT,
                    name="DeiT tiny checkpoint",
                    location=DEIT_CHECKPOINT_URL,
                )
            ],
        ),
        reproduction_gaps=[
            ReproductionGap(category=GapCategory.REPOSITORY, description="Resolve repository."),
            ReproductionGap(category=GapCategory.DATASET_LINK, description="Resolve dataset."),
            ReproductionGap(category=GapCategory.CHECKPOINT, description="Resolve checkpoint."),
        ],
    )


def _discovery(analysis: PaperReproductionAnalysis):
    workflow = DiscoveryWorkflow(
        collection_service=CollectionService(providers=[EmbeddedResourceProvider()]),
        evidence_service=EvidenceService(
            providers=[EmbeddedEvidenceProvider(), DeiTReleaseEvidenceProvider()]
        ),
        verification_service=VerificationService(providers=[EmbeddedVerificationProvider()]),
        ranking_service=RankingService(providers=[EmbeddedRankingProvider()]),
    )
    return workflow.run(analysis)


def _plan(analysis, discovery):
    del analysis
    by_type = {candidate.resource_type: candidate for candidate in discovery.candidate_resources.candidates}
    repo = by_type[ResourceType.OFFICIAL_REPOSITORY]
    dataset = by_type[ResourceType.DATASET_PORTAL]
    checkpoint = by_type[ResourceType.CHECKPOINT]
    base = strategy_with_primary_repo(strategy_id="strategy-deit-v130")
    return base.model_copy(
        update={
            "strategy": base.strategy.model_copy(
                update={"primary_posture": StrategyPosture.HYBRID}
            ),
            "resource_bindings": ResourceBindings(
                bindings=[
                    ResourceBinding(
                        binding_id="binding-primary-repository",
                        candidate_id=repo.candidate_id,
                        role=BindingRole.PRIMARY_REPOSITORY,
                    ),
                    ResourceBinding(
                        binding_id="binding-dataset",
                        candidate_id=dataset.candidate_id,
                        role=BindingRole.DATASET,
                    ),
                    ResourceBinding(
                        binding_id="binding-checkpoint",
                        candidate_id=checkpoint.candidate_id,
                        role=BindingRole.CHECKPOINT,
                    ),
                ],
                anchor_binding_id="binding-primary-repository",
            ),
        }
    )


def _prepare_workspace(root: Path) -> Path:
    paper = root / "2012.12877v2.pdf"
    create_sample_paper_pdf(paper)
    repo = root / "repositories" / "deit"
    (repo / "configs").mkdir(parents=True)
    (repo / "requirements.txt").write_text("", encoding="utf-8")
    (repo / "configs" / "release.json").write_text('{"release_smoke": true}\n', encoding="utf-8")
    workload = (
        "from pathlib import Path\n"
        "import argparse\n"
        "p=argparse.ArgumentParser(); p.add_argument('--config', required=True); p.parse_args()\n"
        "Path('outputs').mkdir(exist_ok=True)\n"
        "Path('outputs/result.json').write_text('deit-release-ok', encoding='utf-8')\n"
    )
    (repo / "main.py").write_text(workload, encoding="utf-8")
    (repo / "compare.py").write_text(
        "from pathlib import Path\n"
        "import argparse\n"
        "p=argparse.ArgumentParser(); p.add_argument('--output', required=True); a=p.parse_args()\n"
        "o=Path(a.output); o.parent.mkdir(parents=True, exist_ok=True)\n"
        "o.write_text('deit-release-report', encoding='utf-8')\n",
        encoding="utf-8",
    )
    dataset = root / "datasets" / "imagenet-release-sample"
    dataset.mkdir(parents=True)
    (dataset / "README.txt").write_text("release fixture", encoding="utf-8")
    checkpoint = root / "checkpoints" / "deit-tiny-release.pth"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"release-checkpoint-fixture")
    return paper


def _pipeline(root: Path, platform_execution: PlatformExecutionService) -> ReproductionPipelineService:
    return ReproductionPipelineService(
        analyze=lambda path: _analysis(Path(path)),
        discover=_discovery,
        plan=_plan,
        platform_execution=platform_execution,
        workspace_root=root,
        persist_planning_artifacts=False,
    )


def _run_interrupt_worker(root: Path) -> None:
    context = RuntimeContext.create()
    bind_workspace_execution_store(context, root)
    executor = ExitAfterFirstAttemptExecutor(create_local_executor(root))

    def engine_factory():
        tracker = InMemoryArtifactTracker(workspace_root=root.as_posix())
        return create_runtime_durable_engine(
            context,
            executor=executor,
            artifact_tracker=tracker,
        )

    service = PlatformExecutionService(context, root, engine_factory=engine_factory)
    _pipeline(root, service).reproduce(root / "2012.12877v2.pdf")
    raise AssertionError("interruption worker did not exit")


class V130ReleaseAcceptanceTest(unittest.TestCase):
    def test_provider_driven_deit_workflow_reaches_durable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper = _prepare_workspace(root)
            result = _pipeline(
                root,
                PlatformExecutionService(RuntimeContext.create(), root),
            ).reproduce(paper)
            self.assertFalse(result.blocked, result.diagnostics)
            self.assertIsNotNone(result.execution)
            assert result.execution is not None
            self.assertEqual(result.execution.status, ExecutionRunStatus.SUCCESS)
            self.assertIsNotNone(result.execution.report)
            evidence = ExecutionEvidenceArtifactStore(root).load()
            self.assertIsNotNone(evidence)
            assert evidence is not None
            repository = evidence.repositories[0]
            self.assertEqual(repository.source_uri, DEIT_REPOSITORY_URL)
            self.assertEqual(repository.revision, DEIT_PINNED_COMMIT)
            self.assertEqual(repository.target_path, "repositories/deit")
            self.assertEqual(repository.entry_script, "main.py")
            self.assertEqual(repository.config_path, "configs/release.json")
            self.assertIn("requirements.txt", repository.manifest_paths)
            self.assertTrue(Path(result.execution.run_directory, "report.json").is_file())
            self.assertTrue((root / "repositories" / "deit" / "outputs" / "result.json").is_file())

    def test_process_interruption_reloads_and_safely_reconciles_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _prepare_workspace(root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tests.test_v130_release_acceptance",
                    "--interrupt-worker",
                    str(root),
                ],
                cwd=Path(__file__).resolve().parents[1],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            )
            self.assertEqual(completed.returncode, 86, completed.stderr)

            context = RuntimeContext.create()
            service = PlatformExecutionService(context, root)
            graph = MaterializationArtifactStore(root).load_materialized_graph()
            self.assertIsNotNone(graph)
            assert graph is not None
            store = bind_workspace_execution_store(context, root)
            resumable = store.list_resumable_runs()
            self.assertEqual(len(resumable), 1)
            run_id = resumable[0].run_id
            before = store.load_snapshot(run_id)
            first_task_id = before.tasks[0].id
            starts_before = sum(
                event.event_type is TraceEventType.TASK_STARTED and event.task_id == first_task_id
                for event in before.trace.events
            )
            self.assertEqual(starts_before, 1)

            outcome = service.run_execution(graph, run_id=run_id, resume=True)
            self.assertTrue(outcome.resumed)
            self.assertEqual(outcome.status, ExecutionRunStatus.RECONCILIATION_REQUIRED)
            after = store.load_snapshot(run_id)
            starts_after = sum(
                event.event_type is TraceEventType.TASK_STARTED and event.task_id == first_task_id
                for event in after.trace.events
            )
            self.assertEqual(starts_after, 1)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--interrupt-worker":
        _run_interrupt_worker(Path(sys.argv[2]))
    unittest.main()
