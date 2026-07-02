"""Extract resource candidates embedded in PaperReproductionAnalysis only."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from models.paper_reproduction_analysis import (
    ArtifactReference,
    ArtifactType,
    DatasetResource,
    ExternalResource,
    GapCategory,
    PaperReproductionAnalysis,
)
from models.research_resource_discovery import (
    CandidateStatus,
    CollectionSource,
    CollectionSourceType,
    DiscoveryProvider,
    NeedCategory,
    Officiality,
    PaperRelation,
    PaperRelationType,
    ProviderInvocationStatus,
    ProviderRecord,
    RelationStrength,
    RepositoryCandidate,
    ResourceIdentity,
    ResourceNeed,
    ResourceType,
)
from ports.collection_provider import CollectionProviderResult
from services.discovery.candidate_merge import normalize_url

_PROVIDER_NAME = "embedded_resource"
_PROVIDER_VERSION = "1.0.0"

_EXTERNAL_RESOURCE_TYPE_MAP: dict[str, ResourceType] = {
    "code_repository": ResourceType.OFFICIAL_REPOSITORY,
    "repository": ResourceType.OFFICIAL_REPOSITORY,
    "official_repository": ResourceType.OFFICIAL_REPOSITORY,
    "community_repository": ResourceType.COMMUNITY_REPOSITORY,
    "project_page": ResourceType.PROJECT_PAGE,
    "project_home": ResourceType.PROJECT_PAGE,
    "checkpoint": ResourceType.CHECKPOINT,
    "configuration": ResourceType.CONFIGURATION,
    "config": ResourceType.CONFIGURATION,
    "documentation": ResourceType.DOCUMENTATION,
    "dataset": ResourceType.DATASET_PORTAL,
    "dataset_portal": ResourceType.DATASET_PORTAL,
    "model_card": ResourceType.MODEL_CARD,
    "huggingface_model": ResourceType.HUGGINGFACE_MODEL,
    "huggingface_dataset": ResourceType.HUGGINGFACE_DATASET,
    "docker_image": ResourceType.DOCKER_IMAGE,
    "release_asset": ResourceType.RELEASE_ASSET,
}

_ARTIFACT_RESOURCE_TYPE_MAP: dict[ArtifactType, ResourceType] = {
    ArtifactType.CHECKPOINT: ResourceType.CHECKPOINT,
    ArtifactType.PRETRAINED_WEIGHT: ResourceType.CHECKPOINT,
    ArtifactType.CONFIG: ResourceType.CONFIGURATION,
    ArtifactType.TOKENIZER: ResourceType.HUGGINGFACE_MODEL,
    ArtifactType.VOCABULARY: ResourceType.HUGGINGFACE_MODEL,
    ArtifactType.CALIBRATION: ResourceType.RELEASE_ASSET,
    ArtifactType.OTHER: ResourceType.CUSTOM,
}

_GAP_TO_NEED_CATEGORY = {
    GapCategory.REPOSITORY: NeedCategory.CODE_REPOSITORY,
    GapCategory.CHECKPOINT: NeedCategory.CHECKPOINT,
    GapCategory.CONFIG: NeedCategory.CONFIG,
    GapCategory.DATASET_LINK: NeedCategory.DATASET,
    GapCategory.HYPERPARAMETER: NeedCategory.EVALUATION_ASSET,
    GapCategory.EVALUATION_DETAIL: NeedCategory.EVALUATION_ASSET,
    GapCategory.IMPLEMENTATION_DETAIL: NeedCategory.DOCUMENTATION,
    GapCategory.OTHER: NeedCategory.EVALUATION_ASSET,
}


class EmbeddedResourceProvider:
    """Deterministic collection from analysis-embedded URLs and references only."""

    def collect(self, analysis: PaperReproductionAnalysis) -> CollectionProviderResult:
        now = datetime.now(UTC)
        resource_needs = _derive_resource_needs(analysis)
        need_ids_by_gap = {
            need.analysis_gap_index: need.need_id
            for need in resource_needs
            if need.analysis_gap_index is not None
        }

        candidates: list[RepositoryCandidate] = []
        for resource in analysis.resources.external_resources:
            candidate = _candidate_from_external_resource(
                resource,
                analysis,
                need_ids_by_gap,
                collected_at=now,
            )
            if candidate is not None:
                candidates.append(candidate)
        for dataset in analysis.resources.datasets:
            candidate = _candidate_from_dataset(
                dataset,
                analysis,
                need_ids_by_gap,
                collected_at=now,
            )
            if candidate is not None:
                candidates.append(candidate)
        for artifact in analysis.resources.artifacts:
            candidate = _candidate_from_artifact(
                artifact,
                analysis,
                need_ids_by_gap,
                collected_at=now,
            )
            if candidate is not None:
                candidates.append(candidate)

        outcome = ProviderRecord(
            provider_name=_PROVIDER_NAME,
            provider_version=_PROVIDER_VERSION,
            invoked_at=now,
            status=ProviderInvocationStatus.SUCCESS,
            candidates_contributed=len(candidates),
            evidence_contributed=0,
        )
        return CollectionProviderResult(
            candidates=candidates,
            resource_needs=resource_needs,
            provider_outcomes=[outcome],
        )


def _derive_resource_needs(analysis: PaperReproductionAnalysis) -> list[ResourceNeed]:
    needs: list[ResourceNeed] = []
    for index, gap in enumerate(analysis.reproduction_gaps):
        category = _GAP_TO_NEED_CATEGORY.get(gap.category, NeedCategory.EVALUATION_ASSET)
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


def _candidate_from_external_resource(
    resource: ExternalResource,
    analysis: PaperReproductionAnalysis,
    need_ids_by_gap: dict[int | None, str],
    *,
    collected_at: datetime,
) -> RepositoryCandidate | None:
    url = resource.url.strip()
    if not _is_url(url):
        return None

    resource_type, custom_label = _map_external_resource_type(resource.resource_type)
    need_id = _match_need_for_resource_type(resource_type, need_ids_by_gap, analysis)
    return _build_candidate(
        url=url,
        title=resource.name,
        resource_type=resource_type,
        custom_type_label=custom_label,
        source_type=CollectionSourceType.ANALYSIS_EXTERNAL_RESOURCE,
        source_query=f"resources.external_resources:{resource.name}",
        officiality=Officiality.OFFICIAL
        if resource_type == ResourceType.OFFICIAL_REPOSITORY
        else Officiality.UNKNOWN,
        notes=resource.notes,
        analysis=analysis,
        addresses_needs=[need_id] if need_id else [],
        collected_at=collected_at,
    )


def _candidate_from_dataset(
    dataset: DatasetResource,
    analysis: PaperReproductionAnalysis,
    need_ids_by_gap: dict[int | None, str],
    *,
    collected_at: datetime,
) -> RepositoryCandidate | None:
    url = dataset.link.strip()
    if not _is_url(url):
        return None

    need_id = need_ids_by_gap.get(
        _first_gap_index_for_category(analysis, GapCategory.DATASET_LINK)
    )
    return _build_candidate(
        url=url,
        title=dataset.name,
        resource_type=ResourceType.DATASET_PORTAL,
        custom_type_label=None,
        source_type=CollectionSourceType.ANALYSIS_DATASET_LINK,
        source_query=f"resources.datasets:{dataset.name}",
        officiality=Officiality.UNKNOWN,
        notes=dataset.description,
        analysis=analysis,
        addresses_needs=[need_id] if need_id else [],
        collected_at=collected_at,
    )


def _candidate_from_artifact(
    artifact: ArtifactReference,
    analysis: PaperReproductionAnalysis,
    need_ids_by_gap: dict[int | None, str],
    *,
    collected_at: datetime,
) -> RepositoryCandidate | None:
    url = artifact.location.strip()
    if not _is_url(url):
        return None

    resource_type = _ARTIFACT_RESOURCE_TYPE_MAP.get(artifact.artifact_type, ResourceType.CUSTOM)
    gap_category = {
        ResourceType.CHECKPOINT: GapCategory.CHECKPOINT,
        ResourceType.CONFIGURATION: GapCategory.CONFIG,
    }.get(resource_type)
    need_id = (
        need_ids_by_gap.get(_first_gap_index_for_category(analysis, gap_category))
        if gap_category
        else None
    )
    return _build_candidate(
        url=url,
        title=artifact.name,
        resource_type=resource_type,
        custom_type_label=artifact.artifact_type.value
        if resource_type == ResourceType.CUSTOM
        else None,
        source_type=CollectionSourceType.ANALYSIS_ARTIFACT,
        source_query=f"resources.artifacts:{artifact.name}",
        officiality=Officiality.UNKNOWN,
        notes=artifact.notes,
        analysis=analysis,
        addresses_needs=[need_id] if need_id else [],
        collected_at=collected_at,
    )


def _build_candidate(
    *,
    url: str,
    title: str,
    resource_type: ResourceType,
    custom_type_label: str | None,
    source_type: CollectionSourceType,
    source_query: str,
    officiality: Officiality,
    notes: str,
    analysis: PaperReproductionAnalysis,
    addresses_needs: list[str],
    collected_at: datetime,
) -> RepositoryCandidate:
    normalized = normalize_url(url)
    provider, native_id = _provider_identity(url, normalized)
    candidate_id = _candidate_id(normalized or url)

    return RepositoryCandidate(
        candidate_id=candidate_id,
        identity=ResourceIdentity(
            provider=provider,
            provider_native_id=native_id,
            normalized_url=normalized,
        ),
        provider=provider,
        resource_type=resource_type,
        tier=1 if resource_type in _TIER_ONE_TYPES else 2,
        url=url,
        title=title,
        officiality=officiality,
        paper_relation=PaperRelation(
            relation_type=PaperRelationType.CITED_IN_PAPER,
            relation_strength=RelationStrength.EXPLICIT,
            matching_signals=[f"analysis_field:{source_query}"],
        ),
        collection_source=CollectionSource(
            source_type=source_type,
            provider_name=_PROVIDER_NAME,
            source_query=source_query,
        ),
        status=CandidateStatus.COLLECTED,
        confidence=1.0,
        addresses_needs=addresses_needs,
        notes=notes,
        collected_at=collected_at,
        custom_type_label=custom_type_label,
    )


_TIER_ONE_TYPES = {
    ResourceType.OFFICIAL_REPOSITORY,
    ResourceType.COMMUNITY_REPOSITORY,
    ResourceType.PROJECT_PAGE,
    ResourceType.CHECKPOINT,
    ResourceType.CONFIGURATION,
    ResourceType.DOCUMENTATION,
}


def _map_external_resource_type(resource_type: str) -> tuple[ResourceType, str | None]:
    normalized = resource_type.strip().casefold().replace("-", "_").replace(" ", "_")
    mapped = _EXTERNAL_RESOURCE_TYPE_MAP.get(normalized)
    if mapped is not None:
        return mapped, None
    return ResourceType.CUSTOM, resource_type.strip() or None


def _match_need_for_resource_type(
    resource_type: ResourceType,
    need_ids_by_gap: dict[int | None, str],
    analysis: PaperReproductionAnalysis,
) -> str | None:
    gap_category = {
        ResourceType.OFFICIAL_REPOSITORY: GapCategory.REPOSITORY,
        ResourceType.COMMUNITY_REPOSITORY: GapCategory.REPOSITORY,
        ResourceType.CHECKPOINT: GapCategory.CHECKPOINT,
        ResourceType.CONFIGURATION: GapCategory.CONFIG,
        ResourceType.DATASET_PORTAL: GapCategory.DATASET_LINK,
        ResourceType.PROJECT_PAGE: GapCategory.REPOSITORY,
    }.get(resource_type)
    if gap_category is None:
        return None
    return need_ids_by_gap.get(_first_gap_index_for_category(analysis, gap_category))


def _first_gap_index_for_category(
    analysis: PaperReproductionAnalysis,
    category: GapCategory | None,
) -> int | None:
    if category is None:
        return None
    for index, gap in enumerate(analysis.reproduction_gaps):
        if gap.category == category:
            return index
    return None


def _provider_identity(url: str, normalized_url: str) -> tuple[DiscoveryProvider, str]:
    host = urlparse_host(normalized_url or url)
    if "github.com" in host:
        match = re.match(r"https?://[^/]+/([^/]+/[^/]+)", normalized_url or url)
        native = match.group(1).rstrip("/") if match else ""
        if native.endswith(".git"):
            native = native[:-4]
        return DiscoveryProvider.GITHUB, native
    if "gitlab.com" in host:
        return DiscoveryProvider.GITLAB, normalized_url or url
    if "huggingface.co" in host:
        return DiscoveryProvider.HUGGINGFACE, normalized_url or url
    if url.startswith("http://") or url.startswith("https://"):
        return DiscoveryProvider.HTTP, normalized_url or url
    return DiscoveryProvider.PAPER_LINK, normalized_url or url


def urlparse_host(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc.lower()


def _candidate_id(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"embedded-{digest}"


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")
