"""Representative paper fixtures for decision-quality regression benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from models.execution_strategy import ReuseMode, StrategyPosture
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import NeedCategory


@dataclass(frozen=True)
class DecisionBenchmarkExpectation:
    """Expected decision outcomes for a benchmark case."""

    min_repository_confidence: float = 0.0
    require_repository_selection: bool = False
    posture: StrategyPosture | None = None
    allowed_postures: frozenset[StrategyPosture] | None = None
    forbid_posture: StrategyPosture | None = None
    min_bindings: int = 0
    reuse_mode: ReuseMode | None = None
    generation_required: bool | None = None
    min_selection_count: int = 0


@dataclass(frozen=True)
class DecisionBenchmarkCase:
    name: str
    analysis_factory: Callable[[], PaperReproductionAnalysis]
    expectation: DecisionBenchmarkExpectation
    paper_label: str = ""


def benchmark_cases() -> tuple[DecisionBenchmarkCase, ...]:
    from tests.test_discovery_collection import _analysis_with_embedded_resources

    return (
        DecisionBenchmarkCase(
            name="resnet_official_repo_embedded",
            paper_label="ResNet (1512.03385)",
            analysis_factory=_analysis_with_embedded_resources,
            expectation=DecisionBenchmarkExpectation(
                require_repository_selection=True,
                min_repository_confidence=0.6,
                posture=StrategyPosture.OFFICIAL_REPOSITORY,
                forbid_posture=StrategyPosture.GREENFIELD,
                min_bindings=1,
                reuse_mode=ReuseMode.AS_IS,
                generation_required=False,
                min_selection_count=1,
            ),
        ),
        DecisionBenchmarkCase(
            name="resnet_hybrid_checkpoint_gap",
            paper_label="ResNet with checkpoint gap",
            analysis_factory=_resnet_with_checkpoint_gap,
            expectation=DecisionBenchmarkExpectation(
                require_repository_selection=True,
                allowed_postures=frozenset(
                    {StrategyPosture.OFFICIAL_REPOSITORY, StrategyPosture.HYBRID}
                ),
                forbid_posture=StrategyPosture.GREENFIELD,
                min_bindings=1,
                min_selection_count=1,
            ),
        ),
        DecisionBenchmarkCase(
            name="no_resources_greenfield",
            paper_label="Paper without embedded resources",
            analysis_factory=_empty_analysis,
            expectation=DecisionBenchmarkExpectation(
                posture=StrategyPosture.GREENFIELD,
                min_bindings=0,
                reuse_mode=ReuseMode.NOT_APPLICABLE,
                generation_required=True,
            ),
        ),
    )


def _empty_analysis() -> PaperReproductionAnalysis:
    from models.paper_reproduction_analysis import AnalysisGoal, PaperMetadata

    return PaperReproductionAnalysis(
        metadata=PaperMetadata(title="Minimal Paper", arxiv_id="0000.00000"),
        goal=AnalysisGoal(research_goal="Reproduce baseline."),
    )


def _resnet_with_checkpoint_gap() -> PaperReproductionAnalysis:
    from models.paper_reproduction_analysis import (
        AnalysisResources,
        ArtifactReference,
        ArtifactType,
        GapCategory,
        ReproductionGap,
    )
    from tests.test_discovery_collection import _analysis_with_embedded_resources

    analysis = _analysis_with_embedded_resources()
    return analysis.model_copy(
        update={
            "reproduction_gaps": [
                *analysis.reproduction_gaps,
                ReproductionGap(
                    category=GapCategory.CHECKPOINT,
                    description="Pretrained weights not verified accessible.",
                ),
            ],
            "resources": AnalysisResources(
                datasets=list(analysis.resources.datasets),
                external_resources=list(analysis.resources.external_resources),
                artifacts=[
                    ArtifactReference(
                        artifact_type=ArtifactType.PRETRAINED_WEIGHT,
                        name="ResNet-50 weights",
                        location="",
                    )
                ],
            ),
        }
    )


def repository_selection_confidence(discovery, category: NeedCategory = NeedCategory.CODE_REPOSITORY) -> float:
    for selection in discovery.selection.selections:
        if selection.resource_need.need_category == category:
            return selection.confidence
    return 0.0
