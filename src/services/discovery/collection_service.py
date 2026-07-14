"""Discovery collection service."""

from __future__ import annotations

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResourceNeed, RepositoryCandidate
from ports.collection_provider import CollectionProvider, CollectionProviderResult
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.github.collection import GitHubCollectionProvider
from providers.noop.collection import NoOpCollectionProvider
from services.discovery.candidate_merge import merge_candidates


class CollectionService:
    """Orchestrates collection providers; workflow depends on this service only."""

    def __init__(self, providers: list[CollectionProvider] | None = None) -> None:
        self._providers = list(providers) if providers is not None else _default_providers()

    def collect(self, analysis: PaperReproductionAnalysis) -> CollectionProviderResult:
        merged_candidates: list[RepositoryCandidate] = []
        needs_by_id: dict[str, ResourceNeed] = {}
        provider_outcomes = []

        for provider in self._providers:
            result = provider.collect(analysis)
            provider_outcomes.extend(result.provider_outcomes)
            for need in result.resource_needs:
                needs_by_id.setdefault(need.need_id, need)
            merged_candidates = merge_candidates(merged_candidates, result.candidates)

        if not needs_by_id:
            needs_by_id.update(
                {need.need_id: need for need in _derive_resource_needs_from_gaps(analysis)}
            )

        return CollectionProviderResult(
            candidates=merged_candidates,
            resource_needs=list(needs_by_id.values()),
            provider_outcomes=provider_outcomes,
        )

    @classmethod
    def default(cls) -> CollectionService:
        return cls(providers=_default_providers())


def _default_providers() -> list[CollectionProvider]:
    return [
        EmbeddedResourceProvider(),
        GitHubCollectionProvider(),
        NoOpCollectionProvider(),
    ]


def _derive_resource_needs_from_gaps(
    analysis: PaperReproductionAnalysis,
) -> list[ResourceNeed]:
    from models.paper_reproduction_analysis import GapCategory
    from models.research_resource_discovery import NeedCategory

    mapping = {
        GapCategory.REPOSITORY: NeedCategory.CODE_REPOSITORY,
        GapCategory.CHECKPOINT: NeedCategory.CHECKPOINT,
        GapCategory.CONFIG: NeedCategory.CONFIG,
        GapCategory.DATASET_LINK: NeedCategory.DATASET,
        GapCategory.HYPERPARAMETER: NeedCategory.EVALUATION_ASSET,
        GapCategory.EVALUATION_DETAIL: NeedCategory.EVALUATION_ASSET,
        GapCategory.IMPLEMENTATION_DETAIL: NeedCategory.DOCUMENTATION,
        GapCategory.OTHER: NeedCategory.EVALUATION_ASSET,
    }

    needs: list[ResourceNeed] = []
    for index, gap in enumerate(analysis.reproduction_gaps):
        category = mapping.get(gap.category, NeedCategory.EVALUATION_ASSET)
        needs.append(
            ResourceNeed(
                need_id=f"need-{gap.category.value}-{index}",
                need_category=category,
                derived_from_analysis_gap=True,
                analysis_gap_index=index,
                required_for_scope=[analysis.goal.scope.value],
                description=gap.description,
            )
        )
    return needs
