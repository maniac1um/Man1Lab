"""Golden benchmark analysis fixtures for decision-quality regression tests."""

from __future__ import annotations

from dataclasses import dataclass

from models.execution_strategy import ReuseMode, StrategyPosture
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
from models.research_resource_discovery import NeedCategory
from providers.embedded.decision_foundation.risk_decision import ReadinessLevel


@dataclass(frozen=True)
class GoldenBenchmarkExpectation:
    """Expected decision outputs for a benchmark paper analysis."""

    name: str
    paper_id: str
    expected_posture: StrategyPosture
    min_repository_selection_confidence: float
    min_binding_count: int
    expected_reuse_mode: ReuseMode
    min_execution_readiness: ReadinessLevel
    require_repository_selection: bool = True
    require_non_greenfield_when_repo: bool = True


def resnet_official_analysis() -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(
            title="Deep Residual Learning for Image Recognition",
            arxiv_id="1512.03385",
        ),
        goal=AnalysisGoal(
            scope=ReproductionScope.TRAINING,
            research_goal="Reproduce ResNet training on ImageNet.",
        ),
        resources=AnalysisResources(
            datasets=[
                DatasetResource(
                    name="ImageNet",
                    link="https://image-net.org/challenges/LSVRC/2012/",
                    description="Training dataset",
                )
            ],
            external_resources=[
                ExternalResource(
                    resource_type="code_repository",
                    name="official-release",
                    url="https://github.com/KaimingHe/deep-residual-networks",
                    notes="Paper-stated repository",
                ),
            ],
        ),
        reproduction_gaps=[
            ReproductionGap(
                category=GapCategory.REPOSITORY,
                description="Repository URL cited in analysis resources.",
            ),
            ReproductionGap(
                category=GapCategory.DATASET_LINK,
                description="Dataset portal link cited in analysis resources.",
            ),
        ],
    )


def attention_official_analysis() -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(
            title="Attention Is All You Need",
            arxiv_id="1706.03762",
        ),
        goal=AnalysisGoal(
            scope=ReproductionScope.TRAINING,
            research_goal="Reproduce Transformer training.",
        ),
        resources=AnalysisResources(
            external_resources=[
                ExternalResource(
                    resource_type="code_repository",
                    name="tensor2tensor",
                    url="https://github.com/tensorflow/tensor2tensor",
                    notes="Reference implementation",
                ),
            ],
        ),
        reproduction_gaps=[
            ReproductionGap(
                category=GapCategory.REPOSITORY,
                description="Repository URL cited in analysis resources.",
            ),
        ],
    )


def community_fork_analysis() -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(
            title="Community Reimplementation Study",
            arxiv_id="0000.00001",
        ),
        goal=AnalysisGoal(
            scope=ReproductionScope.INFERENCE,
            research_goal="Reproduce inference using a community fork.",
        ),
        resources=AnalysisResources(
            external_resources=[
                ExternalResource(
                    resource_type="community_repository",
                    name="community-resnet",
                    url="https://github.com/example/community-resnet",
                    notes="Community reimplementation",
                ),
            ],
        ),
        reproduction_gaps=[
            ReproductionGap(
                category=GapCategory.REPOSITORY,
                description="Community repository cited in analysis resources.",
            ),
        ],
    )


def hybrid_missing_checkpoint_analysis() -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(
            title="Model With Missing Checkpoint",
            arxiv_id="0000.00002",
        ),
        goal=AnalysisGoal(
            scope=ReproductionScope.TRAINING,
            research_goal="Reproduce training with official code but missing checkpoint.",
        ),
        resources=AnalysisResources(
            external_resources=[
                ExternalResource(
                    resource_type="code_repository",
                    name="official-code",
                    url="https://github.com/example/official-model",
                    notes="Official code release",
                ),
            ],
        ),
        reproduction_gaps=[
            ReproductionGap(
                category=GapCategory.REPOSITORY,
                description="Repository URL cited in analysis resources.",
            ),
            ReproductionGap(
                category=GapCategory.CHECKPOINT,
                description="Pretrained checkpoint not provided in paper resources.",
            ),
        ],
    )


def greenfield_no_resources_analysis() -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(
            title="Theoretical Paper Without Artifacts",
            arxiv_id="0000.00003",
        ),
        goal=AnalysisGoal(
            scope=ReproductionScope.FULL_REPRODUCTION,
            research_goal="Reproduce results without published artifacts.",
        ),
        reproduction_gaps=[
            ReproductionGap(
                category=GapCategory.REPOSITORY,
                description="Paper provides no repository URL.",
            ),
        ],
    )


RESNET_OFFICIAL = GoldenBenchmarkExpectation(
    name="resnet_official",
    paper_id="1512.03385",
    expected_posture=StrategyPosture.OFFICIAL_REPOSITORY,
    min_repository_selection_confidence=0.85,
    min_binding_count=1,
    expected_reuse_mode=ReuseMode.AS_IS,
    min_execution_readiness=ReadinessLevel.READY,
)

ATTENTION_OFFICIAL = GoldenBenchmarkExpectation(
    name="attention_official",
    paper_id="1706.03762",
    expected_posture=StrategyPosture.OFFICIAL_REPOSITORY,
    min_repository_selection_confidence=0.85,
    min_binding_count=1,
    expected_reuse_mode=ReuseMode.AS_IS,
    min_execution_readiness=ReadinessLevel.READY,
)

COMMUNITY_FORK = GoldenBenchmarkExpectation(
    name="community_fork",
    paper_id="0000.00001",
    expected_posture=StrategyPosture.COMMUNITY_FORK,
    min_repository_selection_confidence=0.85,
    min_binding_count=1,
    expected_reuse_mode=ReuseMode.AS_IS,
    min_execution_readiness=ReadinessLevel.PARTIAL,
)

HYBRID_MISSING_CHECKPOINT = GoldenBenchmarkExpectation(
    name="hybrid_missing_checkpoint",
    paper_id="0000.00002",
    expected_posture=StrategyPosture.HYBRID,
    min_repository_selection_confidence=0.85,
    min_binding_count=1,
    expected_reuse_mode=ReuseMode.HYBRID_COMPONENTS,
    min_execution_readiness=ReadinessLevel.PARTIAL,
)

GREENFIELD_NO_RESOURCES = GoldenBenchmarkExpectation(
    name="greenfield_no_resources",
    paper_id="0000.00003",
    expected_posture=StrategyPosture.GREENFIELD,
    min_repository_selection_confidence=0.0,
    min_binding_count=0,
    expected_reuse_mode=ReuseMode.NOT_APPLICABLE,
    min_execution_readiness=ReadinessLevel.NOT_READY,
    require_repository_selection=False,
    require_non_greenfield_when_repo=False,
)

GOLDEN_BENCHMARKS: tuple[tuple[GoldenBenchmarkExpectation, callable], ...] = (
    (RESNET_OFFICIAL, resnet_official_analysis),
    (ATTENTION_OFFICIAL, attention_official_analysis),
    (COMMUNITY_FORK, community_fork_analysis),
    (HYBRID_MISSING_CHECKPOINT, hybrid_missing_checkpoint_analysis),
    (GREENFIELD_NO_RESOURCES, greenfield_no_resources_analysis),
)

_READINESS_ORDER = {
    ReadinessLevel.NOT_READY: 0,
    ReadinessLevel.UNKNOWN: 1,
    ReadinessLevel.PARTIAL: 2,
    ReadinessLevel.READY: 3,
}


def readiness_at_least(actual: ReadinessLevel, minimum: ReadinessLevel) -> bool:
    return _READINESS_ORDER[actual] >= _READINESS_ORDER[minimum]


def repository_selection(discovery):
    for selection in discovery.selection.selections:
        if selection.resource_need.need_category == NeedCategory.CODE_REPOSITORY:
            return selection
    return None
