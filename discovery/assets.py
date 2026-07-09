"""Build unified ResearchAsset collection from discovery candidates and selections."""

from __future__ import annotations

from models.explainable_confidence import ExplainableConfidence
from models.research_resource_discovery import (
    ResearchAsset,
    ResearchAssetCollection,
    ResearchAssetType,
    RepositoryCandidate,
    ResourceType,
    SelectionResult,
)

_RESOURCE_TYPE_TO_ASSET_TYPE: dict[ResourceType, ResearchAssetType] = {
    ResourceType.OFFICIAL_REPOSITORY: ResearchAssetType.REPOSITORY,
    ResourceType.COMMUNITY_REPOSITORY: ResearchAssetType.REPOSITORY,
    ResourceType.PROJECT_PAGE: ResearchAssetType.REPOSITORY,
    ResourceType.CHECKPOINT: ResearchAssetType.CHECKPOINT_WEIGHTS,
    ResourceType.HUGGINGFACE_MODEL: ResearchAssetType.CHECKPOINT_WEIGHTS,
    ResourceType.RELEASE_ASSET: ResearchAssetType.CHECKPOINT_WEIGHTS,
    ResourceType.DATASET_PORTAL: ResearchAssetType.DATASET,
    ResourceType.HUGGINGFACE_DATASET: ResearchAssetType.DATASET,
    ResourceType.ZENODO_RECORD: ResearchAssetType.DATASET,
    ResourceType.FIGSHARE_DATASET: ResearchAssetType.DATASET,
    ResourceType.CONFIGURATION: ResearchAssetType.CONFIGURATION,
    ResourceType.DOCKER_IMAGE: ResearchAssetType.DOCKER_IMAGE,
    ResourceType.PYPI_PACKAGE: ResearchAssetType.REQUIREMENTS,
    ResourceType.CONDA_PACKAGE: ResearchAssetType.ENVIRONMENT,
    ResourceType.DOCUMENTATION: ResearchAssetType.DOCUMENTATION,
    ResourceType.MODEL_CARD: ResearchAssetType.DOCUMENTATION,
    ResourceType.PAPERS_WITH_CODE_ENTRY: ResearchAssetType.BENCHMARK,
    ResourceType.COLAB_NOTEBOOK: ResearchAssetType.EVALUATION_SCRIPT,
    ResourceType.INSTITUTIONAL_MIRROR: ResearchAssetType.REPOSITORY,
    ResourceType.CUSTOM: ResearchAssetType.DOCUMENTATION,
}


def map_resource_type_to_asset_type(resource_type: ResourceType) -> ResearchAssetType:
    return _RESOURCE_TYPE_TO_ASSET_TYPE.get(resource_type, ResearchAssetType.DOCUMENTATION)


def build_research_assets(
    candidates: list[RepositoryCandidate],
    selection: SelectionResult,
) -> ResearchAssetCollection:
    """Normalize candidates into ResearchAsset records with selection markers."""
    primary_ids = {
        record.primary_candidate_id
        for record in selection.selections
        if record.primary_candidate_id is not None
    }
    fallback_ids = {
        candidate_id
        for record in selection.selections
        for candidate_id in record.fallback_candidate_ids
    }
    composition_by_candidate = _selection_confidence_by_candidate(selection)

    assets: list[ResearchAsset] = []
    by_type: dict[str, list[str]] = {}
    for candidate in candidates:
        asset_type = map_resource_type_to_asset_type(candidate.resource_type)
        composition = composition_by_candidate.get(candidate.candidate_id, ExplainableConfidence())
        asset = ResearchAsset(
            asset_id=candidate.candidate_id,
            candidate_id=candidate.candidate_id,
            asset_type=asset_type,
            resource_type=candidate.resource_type,
            identity=candidate.identity,
            url=candidate.url,
            title=candidate.title,
            officiality=candidate.officiality,
            status=candidate.status,
            addresses_needs=list(candidate.addresses_needs),
            confidence=composition.overall if composition.overall > 0 else candidate.confidence,
            confidence_composition=composition,
            selected_primary=candidate.candidate_id in primary_ids,
            selected_fallback=candidate.candidate_id in fallback_ids,
            collected_at=candidate.collected_at,
        )
        assets.append(asset)
        by_type.setdefault(asset_type.value, []).append(asset.asset_id)

    return ResearchAssetCollection(
        assets=assets,
        indexes={key: ids for key, ids in ((f"asset_type:{k}", v) for k, v in by_type.items())}
        if by_type
        else {},
    )


def _selection_confidence_by_candidate(selection: SelectionResult) -> dict[str, ExplainableConfidence]:
    mapping: dict[str, ExplainableConfidence] = {}
    for record in selection.selections:
        if record.primary_candidate_id is not None:
            mapping[record.primary_candidate_id] = record.confidence_composition
    return mapping
