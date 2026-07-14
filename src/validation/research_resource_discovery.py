from __future__ import annotations

from datetime import datetime

from models.explainable_confidence import ConfidenceContribution, ExplainableConfidence
from models.research_resource_discovery import (
    SCHEMA_VERSION,
    AnalysisGapSnapshot,
    AnalysisReference,
    CandidateResources,
    CandidateStatus,
    CollectionSource,
    CollectionSourceType,
    DiscoveryGap,
    DiscoveryGapType,
    DiscoveryGaps,
    DiscoveryMetadata,
    DiscoveryProvenance,
    DiscoveryProvider,
    DiscoveryStatistics,
    DiscoveryStatus,
    DimensionResult,
    EvidenceCollection,
    EvidencePolarity,
    EvidenceRecord,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceType,
    FetchStatus,
    GapSeverity,
    InvocationReason,
    ManualOverride,
    NeedCategory,
    ObservedFact,
    Officiality,
    PaperRelation,
    PaperRelationType,
    ProviderInvocationStatus,
    ProviderRecord,
    RankList,
    RankingFactor,
    RankingResult,
    RankScore,
    RecommendedAction,
    RelationStrength,
    RepositoryCandidate,
    ResearchResourceDiscovery,
    ResourceIdentity,
    ResourceNeed,
    ResearchAsset,
    ResearchAssetCollection,
    ResearchAssetType,
    ResourceType,
    SelectionReason,
    SelectionRecord,
    SelectionResult,
    VerificationCollection,
    VerificationDimension,
    VerificationDimensionName,
    VerificationRecord,
    VerificationStatus,
)
from validation.exceptions import DiscoveryValidationError

_ALLOWED_SELECTION_VERIFICATION = {VerificationStatus.PASS, VerificationStatus.PARTIAL}


def validate_discovery_dict(data: dict) -> None:
    if not isinstance(data, dict):
        raise DiscoveryValidationError("Discovery data must be a dict")

    _require_dict(data, "metadata")
    _require_dict(data, "analysis_reference")
    _validate_schema_version(data.get("schema_version"))

    metadata = data["metadata"]
    _require_non_empty_string(metadata, "discovery_id", path="metadata")
    _validate_discovery_status(metadata.get("status"), path="metadata.status")
    _validate_invocation_reason(metadata.get("invocation_reason"), path="metadata.invocation_reason")

    candidates = _candidate_list(data)
    evidence_records = _evidence_list(data)
    verification_records = _verification_list(data)
    rank_lists = _rank_list_list(data)
    selections = _selection_list(data)
    gaps = _gap_list(data)

    _validate_candidate_uniqueness(candidates)
    _validate_reference_integrity(
        candidates=candidates,
        evidence_records=evidence_records,
        verification_records=verification_records,
        rank_lists=rank_lists,
        selections=selections,
        gaps=gaps,
    )
    _validate_metadata_counts(metadata, candidates, selections, gaps)
    _validate_selection_records(selections, candidates, verification_records, rank_lists)
    _validate_gap_records(gaps)


def normalize_discovery_dict(data: dict) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError("Discovery data must be a dict")

    metadata = _normalize_metadata(data.get("metadata", {}))
    provenance = _normalize_provenance(data.get("provenance", {}))
    analysis_reference = _normalize_analysis_reference(data.get("analysis_reference", {}))
    candidate_resources = _normalize_candidate_resources(data.get("candidate_resources", {}))
    evidence = _normalize_evidence(data.get("evidence", {}))
    verification = _normalize_verification(data.get("verification", {}))
    ranking = _normalize_ranking(data.get("ranking", {}))
    selection = _normalize_selection(data.get("selection", {}))
    discovery_gaps = _normalize_discovery_gaps(data.get("discovery_gaps", {}))
    statistics = _normalize_statistics(data.get("statistics", {}))
    research_assets = _normalize_research_assets(data.get("research_assets", {}))
    schema_version = _normalize_schema_version(data.get("schema_version"))

    return {
        "metadata": metadata,
        "provenance": provenance,
        "analysis_reference": analysis_reference,
        "candidate_resources": candidate_resources,
        "research_assets": research_assets,
        "evidence": evidence,
        "verification": verification,
        "ranking": ranking,
        "selection": selection,
        "discovery_gaps": discovery_gaps,
        "statistics": statistics,
        "schema_version": schema_version,
    }


def build_research_resource_discovery(data: dict) -> ResearchResourceDiscovery:
    validate_discovery_dict(data)
    normalized = normalize_discovery_dict(data)
    return ResearchResourceDiscovery(
        metadata=DiscoveryMetadata(**normalized["metadata"]),
        provenance=DiscoveryProvenance(**normalized["provenance"]),
        analysis_reference=AnalysisReference(**normalized["analysis_reference"]),
        candidate_resources=CandidateResources(**normalized["candidate_resources"]),
        research_assets=ResearchAssetCollection(**normalized["research_assets"]),
        evidence=EvidenceCollection(**normalized["evidence"]),
        verification=VerificationCollection(**normalized["verification"]),
        ranking=RankingResult(**normalized["ranking"]),
        selection=SelectionResult(**normalized["selection"]),
        discovery_gaps=DiscoveryGaps(**normalized["discovery_gaps"]),
        statistics=DiscoveryStatistics(**normalized["statistics"]),
        schema_version=normalized["schema_version"],
    )


def _normalize_metadata(data: dict) -> dict:
    _require_dict_instance(data, "metadata")
    return {
        "discovery_id": _require_non_empty_string(data, "discovery_id", path="metadata"),
        "created_at": _normalize_datetime(data.get("created_at"), path="metadata.created_at"),
        "status": _normalize_discovery_status(data.get("status"), path="metadata.status"),
        "summary": _normalize_optional_string(data.get("summary")),
        "reproduction_scope": _normalize_optional_string(data.get("reproduction_scope"), "unknown"),
        "invocation_reason": _normalize_invocation_reason(
            data.get("invocation_reason"), path="metadata.invocation_reason"
        ),
        "candidate_count": _normalize_int(data.get("candidate_count"), default=0),
        "selection_count": _normalize_int(data.get("selection_count"), default=0),
        "unresolved_gap_count": _normalize_int(data.get("unresolved_gap_count"), default=0),
    }


def _normalize_provenance(data: dict) -> dict:
    if not isinstance(data, dict):
        return {
            "discovery_run_id": "",
            "pipeline_version": "",
            "stage_timestamps": {},
            "providers_used": [],
            "degradation_notes": [],
            "configuration_fingerprint": "",
            "rerun_of": None,
        }

    providers = data.get("providers_used", [])
    if providers is None:
        providers = []
    if not isinstance(providers, list):
        raise DiscoveryValidationError("Invalid field: provenance.providers_used must be a list")

    notes = data.get("degradation_notes", [])
    if notes is None:
        notes = []
    if not isinstance(notes, list):
        raise DiscoveryValidationError("Invalid field: provenance.degradation_notes must be a list")

    timestamps = data.get("stage_timestamps", {})
    if timestamps is None:
        timestamps = {}
    if not isinstance(timestamps, dict):
        raise DiscoveryValidationError("Invalid field: provenance.stage_timestamps must be a dict")

    normalized_timestamps = {
        str(key): _normalize_datetime(value, path=f"provenance.stage_timestamps.{key}")
        for key, value in timestamps.items()
    }

    return {
        "discovery_run_id": _normalize_optional_string(data.get("discovery_run_id")),
        "pipeline_version": _normalize_optional_string(data.get("pipeline_version")),
        "stage_timestamps": normalized_timestamps,
        "providers_used": [_normalize_provider_record(item, index) for index, item in enumerate(providers)],
        "degradation_notes": [
            _normalize_optional_string(item) for item in notes if _normalize_optional_string(item)
        ],
        "configuration_fingerprint": _normalize_optional_string(data.get("configuration_fingerprint")),
        "rerun_of": _normalize_optional_string(data.get("rerun_of")) or None,
    }


def _normalize_analysis_reference(data: dict) -> dict:
    _require_dict_instance(data, "analysis_reference")
    gaps_snapshot = data.get("analysis_gaps_snapshot", [])
    if gaps_snapshot is None:
        gaps_snapshot = []
    if not isinstance(gaps_snapshot, list):
        raise DiscoveryValidationError("Invalid field: analysis_reference.analysis_gaps_snapshot must be a list")

    gaps_addressed = data.get("analysis_gaps_addressed", [])
    if gaps_addressed is None:
        gaps_addressed = []
    if not isinstance(gaps_addressed, list):
        raise DiscoveryValidationError(
            "Invalid field: analysis_reference.analysis_gaps_addressed must be a list"
        )

    return {
        "analysis_schema_version": _require_non_empty_string(
            data, "analysis_schema_version", path="analysis_reference"
        ),
        "paper_title": _require_non_empty_string(data, "paper_title", path="analysis_reference"),
        "arxiv_id": _normalize_optional_string(data.get("arxiv_id")),
        "source_path": _normalize_optional_string(data.get("source_path")) or None,
        "analysis_content_hash": _require_non_empty_string(
            data, "analysis_content_hash", path="analysis_reference"
        ),
        "analysis_gaps_addressed": [
            _normalize_optional_string(item) for item in gaps_addressed if _normalize_optional_string(item)
        ],
        "analysis_gaps_snapshot": [
            _normalize_gap_snapshot(item, index) for index, item in enumerate(gaps_snapshot)
        ],
    }


def _normalize_candidate_resources(data: dict) -> dict:
    if not isinstance(data, dict):
        return {"candidates": [], "indexes": {}}
    candidates = data.get("candidates", [])
    if candidates is None:
        candidates = []
    if not isinstance(candidates, list):
        raise DiscoveryValidationError("Invalid field: candidate_resources.candidates must be a list")
    indexes = data.get("indexes", {})
    if indexes is None:
        indexes = {}
    if not isinstance(indexes, dict):
        raise DiscoveryValidationError("Invalid field: candidate_resources.indexes must be a dict")
    return {
        "candidates": [_normalize_candidate(item, index) for index, item in enumerate(candidates)],
        "indexes": {str(key): list(value) for key, value in indexes.items()},
    }


def _normalize_evidence(data: dict) -> dict:
    if not isinstance(data, dict):
        return {"records": [], "indexes": {}}
    records = data.get("records", [])
    if records is None:
        records = []
    if not isinstance(records, list):
        raise DiscoveryValidationError("Invalid field: evidence.records must be a list")
    indexes = data.get("indexes", {})
    if indexes is None:
        indexes = {}
    if not isinstance(indexes, dict):
        raise DiscoveryValidationError("Invalid field: evidence.indexes must be a dict")
    return {
        "records": [_normalize_evidence_record(item, index) for index, item in enumerate(records)],
        "indexes": {str(key): list(value) for key, value in indexes.items()},
    }


def _normalize_verification(data: dict) -> dict:
    if not isinstance(data, dict):
        return {"records": [], "indexes": {}}
    records = data.get("records", [])
    if records is None:
        records = []
    if not isinstance(records, list):
        raise DiscoveryValidationError("Invalid field: verification.records must be a list")
    indexes = data.get("indexes", {})
    if indexes is None:
        indexes = {}
    if not isinstance(indexes, dict):
        raise DiscoveryValidationError("Invalid field: verification.indexes must be a dict")
    return {
        "records": [_normalize_verification_record(item, index) for index, item in enumerate(records)],
        "indexes": {str(key): list(value) for key, value in indexes.items()},
    }


def _normalize_ranking(data: dict) -> dict:
    if not isinstance(data, dict):
        return {"rank_lists": [], "global_notes": ""}
    rank_lists = data.get("rank_lists", [])
    if rank_lists is None:
        rank_lists = []
    if not isinstance(rank_lists, list):
        raise DiscoveryValidationError("Invalid field: ranking.rank_lists must be a list")
    return {
        "rank_lists": [_normalize_rank_list(item, index) for index, item in enumerate(rank_lists)],
        "global_notes": _normalize_optional_string(data.get("global_notes")),
    }


def _normalize_selection(data: dict) -> dict:
    if not isinstance(data, dict):
        return {
            "selections": [],
            "retained_candidate_policy": "full_candidate_set_preserved",
            "manual_overrides": [],
        }
    selections = data.get("selections", [])
    if selections is None:
        selections = []
    if not isinstance(selections, list):
        raise DiscoveryValidationError("Invalid field: selection.selections must be a list")
    overrides = data.get("manual_overrides", [])
    if overrides is None:
        overrides = []
    if not isinstance(overrides, list):
        raise DiscoveryValidationError("Invalid field: selection.manual_overrides must be a list")
    return {
        "selections": [_normalize_selection_record(item, index) for index, item in enumerate(selections)],
        "retained_candidate_policy": _normalize_optional_string(
            data.get("retained_candidate_policy"), "full_candidate_set_preserved"
        ),
        "manual_overrides": [
            _normalize_manual_override(item, index) for index, item in enumerate(overrides)
        ],
    }


def _normalize_discovery_gaps(data: dict) -> dict:
    if not isinstance(data, dict):
        return {"gaps": [], "analysis_gaps_closed": [], "analysis_gaps_remaining": []}
    gaps = data.get("gaps", [])
    if gaps is None:
        gaps = []
    if not isinstance(gaps, list):
        raise DiscoveryValidationError("Invalid field: discovery_gaps.gaps must be a list")
    closed = data.get("analysis_gaps_closed", [])
    remaining = data.get("analysis_gaps_remaining", [])
    if closed is None:
        closed = []
    if remaining is None:
        remaining = []
    if not isinstance(closed, list) or not isinstance(remaining, list):
        raise DiscoveryValidationError("Invalid field: discovery_gaps closure lists must be lists")
    return {
        "gaps": [_normalize_discovery_gap(item, index) for index, item in enumerate(gaps)],
        "analysis_gaps_closed": [
            _normalize_optional_string(item) for item in closed if _normalize_optional_string(item)
        ],
        "analysis_gaps_remaining": [
            _normalize_optional_string(item) for item in remaining if _normalize_optional_string(item)
        ],
    }


def _normalize_statistics(data: dict) -> dict:
    if not isinstance(data, dict):
        return {
            "candidate_count": 0,
            "selection_count": 0,
            "unresolved_gap_count": 0,
            "evidence_count": 0,
            "verification_count": 0,
        }
    return {
        "candidate_count": _normalize_int(data.get("candidate_count"), default=0),
        "selection_count": _normalize_int(data.get("selection_count"), default=0),
        "unresolved_gap_count": _normalize_int(data.get("unresolved_gap_count"), default=0),
        "evidence_count": _normalize_int(data.get("evidence_count"), default=0),
        "verification_count": _normalize_int(data.get("verification_count"), default=0),
    }


def _normalize_explainable_confidence(data: object) -> dict:
    if not isinstance(data, dict):
        return ExplainableConfidence().model_dump(mode="json")
    contributions = data.get("contributions", [])
    if contributions is None:
        contributions = []
    if not isinstance(contributions, list):
        raise DiscoveryValidationError("Invalid field: confidence_composition.contributions must be a list")
    return {
        "overall": _normalize_float(data.get("overall"), default=0.0),
        "contributions": [
            _normalize_confidence_contribution(item, index) for index, item in enumerate(contributions)
        ],
        "composition_rule": _normalize_optional_string(data.get("composition_rule"), "weighted_sum_capped"),
    }


def _normalize_confidence_contribution(data: object, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid confidence contribution at index {index}")
    return {
        "signal": _require_non_empty_string(data, "signal", path=f"contributions[{index}]"),
        "weight": _normalize_float(data.get("weight"), default=0.0),
        "score": _normalize_float(data.get("score"), default=0.0),
        "contribution": _normalize_float(data.get("contribution"), default=0.0),
        "summary": _normalize_optional_string(data.get("summary")),
    }


def _normalize_research_assets(data: object) -> dict:
    if not isinstance(data, dict):
        return ResearchAssetCollection().model_dump(mode="json")
    assets = data.get("assets", [])
    if assets is None:
        assets = []
    if not isinstance(assets, list):
        raise DiscoveryValidationError("Invalid field: research_assets.assets must be a list")
    indexes = data.get("indexes", {})
    if indexes is None:
        indexes = {}
    if not isinstance(indexes, dict):
        raise DiscoveryValidationError("Invalid field: research_assets.indexes must be a dict")
    return {
        "assets": [_normalize_research_asset(item, index) for index, item in enumerate(assets)],
        "indexes": {
            str(key): _normalize_string_list(value) for key, value in indexes.items()
        },
        "schema_version": _normalize_optional_string(data.get("schema_version"), "1.0"),
    }


def _normalize_research_asset(data: object, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid research asset at index {index}")
    identity = data.get("identity")
    if not isinstance(identity, dict):
        raise DiscoveryValidationError(f"Missing identity for research_assets.assets[{index}]")
    return {
        "asset_id": _require_non_empty_string(data, "asset_id", path=f"research_assets.assets[{index}]"),
        "candidate_id": _require_non_empty_string(data, "candidate_id", path=f"research_assets.assets[{index}]"),
        "asset_type": _normalize_research_asset_type(data.get("asset_type"), index=index),
        "resource_type": _normalize_resource_type(data.get("resource_type"), path=f"research_assets.assets[{index}]"),
        "identity": _normalize_resource_identity(identity, index),
        "url": _normalize_optional_string(data.get("url")),
        "title": _normalize_optional_string(data.get("title")),
        "officiality": _normalize_officiality(data.get("officiality"), path=f"research_assets.assets[{index}]"),
        "status": _normalize_candidate_status(data.get("status"), path=f"research_assets.assets[{index}]"),
        "addresses_needs": _normalize_string_list(data.get("addresses_needs")),
        "confidence": _normalize_float(data.get("confidence"), default=0.0),
        "confidence_composition": _normalize_explainable_confidence(data.get("confidence_composition")),
        "selected_primary": bool(data.get("selected_primary", False)),
        "selected_fallback": bool(data.get("selected_fallback", False)),
        "collected_at": _normalize_optional_datetime(data.get("collected_at")),
    }


def _normalize_research_asset_type(value: object, *, index: int) -> str:
    if isinstance(value, ResearchAssetType):
        return value.value
    if isinstance(value, str) and value in {item.value for item in ResearchAssetType}:
        return value
    raise DiscoveryValidationError(f"Invalid asset_type for research_assets.assets[{index}]")


def _normalize_candidate(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid candidate at index {index}")
    collection_source = data.get("collection_source")
    if not isinstance(collection_source, dict):
        raise DiscoveryValidationError(f"Missing collection_source for candidate[{index}]")
    identity = data.get("identity")
    if not isinstance(identity, dict):
        raise DiscoveryValidationError(f"Missing identity for candidate[{index}]")
    paper_relation = data.get("paper_relation", {})
    if paper_relation is None:
        paper_relation = {}
    if not isinstance(paper_relation, dict):
        raise DiscoveryValidationError(f"Invalid paper_relation for candidate[{index}]")
    extensions = data.get("extensions", {})
    if extensions is None:
        extensions = {}
    if not isinstance(extensions, dict):
        raise DiscoveryValidationError(f"Invalid extensions for candidate[{index}]")
    return {
        "candidate_id": _require_non_empty_string(data, "candidate_id", path=f"candidates[{index}]"),
        "identity": _normalize_resource_identity(identity, index),
        "provider": _normalize_discovery_provider(data.get("provider"), path=f"candidates[{index}].provider"),
        "resource_type": _normalize_resource_type(
            data.get("resource_type"), path=f"candidates[{index}].resource_type"
        ),
        "tier": _normalize_int(data.get("tier"), default=1),
        "url": _normalize_optional_string(data.get("url")),
        "title": _normalize_optional_string(data.get("title")),
        "officiality": _normalize_officiality(data.get("officiality"), path=f"candidates[{index}].officiality"),
        "paper_relation": _normalize_paper_relation(paper_relation),
        "collection_source": _normalize_collection_source(collection_source, index),
        "status": _normalize_candidate_status(data.get("status"), path=f"candidates[{index}].status"),
        "confidence": _normalize_float(data.get("confidence"), default=0.0),
        "related_candidate_ids": _normalize_string_list(data.get("related_candidate_ids")),
        "addresses_needs": _normalize_string_list(data.get("addresses_needs")),
        "notes": _normalize_optional_string(data.get("notes")),
        "collected_at": _normalize_optional_datetime(data.get("collected_at")),
        "extensions": {str(key): str(value) for key, value in extensions.items()},
        "custom_type_label": _normalize_optional_string(data.get("custom_type_label")) or None,
    }


def _normalize_resource_identity(data: dict, index: int) -> dict:
    return {
        "provider": _normalize_discovery_provider(
            data.get("provider"), path=f"candidates[{index}].identity.provider"
        ),
        "provider_native_id": _normalize_optional_string(data.get("provider_native_id")),
        "normalized_url": _normalize_optional_string(data.get("normalized_url")),
        "content_hash": _normalize_optional_string(data.get("content_hash")) or None,
    }


def _normalize_paper_relation(data: dict) -> dict:
    signals = data.get("matching_signals", [])
    if signals is None:
        signals = []
    if not isinstance(signals, list):
        raise DiscoveryValidationError("Invalid field: paper_relation.matching_signals must be a list")
    return {
        "relation_type": _normalize_paper_relation_type(data.get("relation_type")),
        "relation_strength": _normalize_relation_strength(data.get("relation_strength")),
        "matching_signals": [
            _normalize_optional_string(item) for item in signals if _normalize_optional_string(item)
        ],
    }


def _normalize_collection_source(data: dict, index: int) -> dict:
    return {
        "source_type": _normalize_collection_source_type(
            data.get("source_type"), path=f"candidates[{index}].collection_source.source_type"
        ),
        "provider_name": _normalize_optional_string(data.get("provider_name")) or None,
        "source_query": _normalize_optional_string(data.get("source_query")) or None,
        "seed_candidate_id": _normalize_optional_string(data.get("seed_candidate_id")) or None,
    }


def _normalize_evidence_record(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid evidence record at index {index}")
    evidence_source = data.get("evidence_source")
    if not isinstance(evidence_source, dict):
        raise DiscoveryValidationError(f"Missing evidence_source for evidence[{index}]")
    observed_fact = data.get("observed_fact", {})
    if observed_fact is None:
        observed_fact = {}
    if not isinstance(observed_fact, dict):
        raise DiscoveryValidationError(f"Invalid observed_fact for evidence[{index}]")
    return {
        "evidence_id": _require_non_empty_string(data, "evidence_id", path=f"evidence[{index}]"),
        "candidate_id": _require_non_empty_string(data, "candidate_id", path=f"evidence[{index}]"),
        "evidence_type": _normalize_evidence_type(
            data.get("evidence_type"), path=f"evidence[{index}].evidence_type"
        ),
        "evidence_source": _normalize_evidence_source(evidence_source, index),
        "observed_fact": _normalize_observed_fact(observed_fact),
        "polarity": _normalize_evidence_polarity(data.get("polarity")),
        "confidence": _normalize_float(data.get("confidence"), default=0.0),
        "collected_at": _normalize_optional_datetime(data.get("collected_at")),
        "expires_at": _normalize_optional_datetime(data.get("expires_at")),
        "raw_reference": _normalize_optional_string(data.get("raw_reference")) or None,
        "custom_type_label": _normalize_optional_string(data.get("custom_type_label")) or None,
    }


def _normalize_evidence_source(data: dict, index: int) -> dict:
    return {
        "source_kind": _normalize_evidence_source_kind(
            data.get("source_kind"), path=f"evidence[{index}].evidence_source.source_kind"
        ),
        "provider_name": _normalize_optional_string(data.get("provider_name")) or None,
        "uri": _normalize_optional_string(data.get("uri")),
        "fetch_status": _normalize_fetch_status(data.get("fetch_status")),
    }


def _normalize_observed_fact(data: dict) -> dict:
    fields = data.get("fields", data)
    if fields is None:
        fields = {}
    if not isinstance(fields, dict):
        raise DiscoveryValidationError("Invalid field: observed_fact.fields must be a dict")
    extensions = data.get("extensions", {})
    if extensions is None:
        extensions = {}
    if not isinstance(extensions, dict):
        raise DiscoveryValidationError("Invalid field: observed_fact.extensions must be a dict")
    normalized_fields: dict[str, str | int | float | bool] = {}
    for key, value in fields.items():
        if isinstance(value, (str, int, float, bool)):
            normalized_fields[str(key)] = value
    return {
        "fields": normalized_fields,
        "custom_type_label": _normalize_optional_string(data.get("custom_type_label")) or None,
        "extensions": {str(key): str(value) for key, value in extensions.items()},
    }


def _normalize_verification_record(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid verification record at index {index}")
    dimensions = data.get("dimensions", [])
    if dimensions is None:
        dimensions = []
    if not isinstance(dimensions, list):
        raise DiscoveryValidationError(f"Invalid dimensions for verification[{index}]")
    blocking = data.get("blocking_failures", [])
    if blocking is None:
        blocking = []
    if not isinstance(blocking, list):
        raise DiscoveryValidationError(f"Invalid blocking_failures for verification[{index}]")
    return {
        "verification_id": _require_non_empty_string(data, "verification_id", path=f"verification[{index}]"),
        "candidate_id": _require_non_empty_string(data, "candidate_id", path=f"verification[{index}]"),
        "status": _normalize_verification_status(
            data.get("status"), path=f"verification[{index}].status"
        ),
        "dimensions": [
            _normalize_verification_dimension(item, index, dim_index)
            for dim_index, item in enumerate(dimensions)
        ],
        "blocking_failures": [
            _normalize_optional_string(item) for item in blocking if _normalize_optional_string(item)
        ],
        "verified_at": _normalize_optional_datetime(data.get("verified_at")),
        "verifier_version": _normalize_optional_string(data.get("verifier_version")),
    }


def _normalize_verification_dimension(data: dict, rec_index: int, dim_index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(
            f"Invalid verification dimension at verification[{rec_index}].dimensions[{dim_index}]"
        )
    evidence_ids = data.get("evidence_ids", [])
    if evidence_ids is None:
        evidence_ids = []
    if not isinstance(evidence_ids, list):
        raise DiscoveryValidationError("Invalid field: verification dimension evidence_ids must be a list")
    details = data.get("details", {})
    if details is None:
        details = {}
    if not isinstance(details, dict):
        raise DiscoveryValidationError("Invalid field: verification dimension details must be a dict")
    return {
        "dimension": _normalize_verification_dimension_name(data.get("dimension")),
        "result": _normalize_dimension_result(data.get("result")),
        "summary": _normalize_optional_string(data.get("summary")),
        "evidence_ids": [
            _normalize_optional_string(item) for item in evidence_ids if _normalize_optional_string(item)
        ],
        "details": {str(key): str(value) for key, value in details.items()},
    }


def _normalize_rank_list(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid rank list at index {index}")
    resource_need = data.get("resource_need")
    if not isinstance(resource_need, dict):
        raise DiscoveryValidationError(f"Missing resource_need for rank_lists[{index}]")
    scores = data.get("scores", {})
    if scores is None:
        scores = {}
    if not isinstance(scores, dict):
        raise DiscoveryValidationError(f"Invalid scores for rank_lists[{index}]")
    normalized_scores = {
        str(candidate_id): _normalize_rank_score(score, index, str(candidate_id))
        for candidate_id, score in scores.items()
    }
    return {
        "rank_list_id": _require_non_empty_string(data, "rank_list_id", path=f"rank_lists[{index}]"),
        "resource_need": _normalize_resource_need(resource_need, index),
        "ordered_candidate_ids": _normalize_string_list(data.get("ordered_candidate_ids")),
        "scores": normalized_scores,
        "ranking_factors_summary": _normalize_optional_string(data.get("ranking_factors_summary")),
        "eligible_candidate_ids": _normalize_string_list(data.get("eligible_candidate_ids")),
        "created_at": _normalize_optional_datetime(data.get("created_at")),
    }


def _normalize_rank_score(data: dict | object, list_index: int, candidate_id: str) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(
            f"Invalid rank score for candidate {candidate_id} in rank_lists[{list_index}]"
        )
    factor_scores = data.get("factor_scores", {})
    if factor_scores is None:
        factor_scores = {}
    if not isinstance(factor_scores, dict):
        raise DiscoveryValidationError("Invalid field: rank score factor_scores must be a dict")
    factors = data.get("ranking_factors", [])
    if factors is None:
        factors = []
    if not isinstance(factors, list):
        raise DiscoveryValidationError("Invalid field: rank score ranking_factors must be a list")
    return {
        "candidate_id": _normalize_optional_string(data.get("candidate_id"), candidate_id),
        "total_score": _normalize_float(data.get("total_score"), default=0.0),
        "factor_scores": {str(key): _normalize_float(value, default=0.0) for key, value in factor_scores.items()},
        "ranking_factors": [
            _normalize_ranking_factor(item, list_index, factor_index)
            for factor_index, item in enumerate(factors)
        ],
    }


def _normalize_ranking_factor(data: dict, list_index: int, factor_index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(
            f"Invalid ranking factor at rank_lists[{list_index}].ranking_factors[{factor_index}]"
        )
    return {
        "name": _require_non_empty_string(data, "name", path="ranking_factor"),
        "score": _normalize_float(data.get("score"), default=0.0),
        "weight": _normalize_float(data.get("weight"), default=0.0),
        "summary": _normalize_optional_string(data.get("summary")),
    }


def _normalize_selection_record(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid selection at index {index}")
    resource_need = data.get("resource_need")
    if not isinstance(resource_need, dict):
        raise DiscoveryValidationError(f"Missing resource_need for selections[{index}]")
    selection_reason = data.get("selection_reason", {})
    if selection_reason is None:
        selection_reason = {}
    if not isinstance(selection_reason, dict):
        raise DiscoveryValidationError(f"Invalid selection_reason for selections[{index}]")
    snapshot = data.get("verification_snapshot", {})
    if snapshot is None:
        snapshot = {}
    if not isinstance(snapshot, dict):
        raise DiscoveryValidationError(f"Invalid verification_snapshot for selections[{index}]")
    return {
        "selection_id": _require_non_empty_string(data, "selection_id", path=f"selections[{index}]"),
        "resource_need": _normalize_resource_need(resource_need, index),
        "primary_candidate_id": _normalize_optional_string(data.get("primary_candidate_id")) or None,
        "fallback_candidate_ids": _normalize_string_list(data.get("fallback_candidate_ids")),
        "selection_reason": _normalize_selection_reason(selection_reason),
        "confidence": _normalize_float(data.get("confidence"), default=0.0),
        "confidence_composition": _normalize_explainable_confidence(data.get("confidence_composition")),
        "selected_at": _normalize_optional_datetime(data.get("selected_at")),
        "rank_list_id": _normalize_optional_string(data.get("rank_list_id")),
        "verification_snapshot": {str(key): str(value) for key, value in snapshot.items()},
    }


def _normalize_selection_reason(data: dict) -> dict:
    deciding = data.get("deciding_factors", [])
    if deciding is None:
        deciding = []
    if not isinstance(deciding, list):
        raise DiscoveryValidationError("Invalid field: selection_reason.deciding_factors must be a list")
    evidence_ids = data.get("evidence_ids", [])
    if evidence_ids is None:
        evidence_ids = []
    if not isinstance(evidence_ids, list):
        raise DiscoveryValidationError("Invalid field: selection_reason.evidence_ids must be a list")
    rejected = data.get("rejected_candidate_ids", [])
    if rejected is None:
        rejected = []
    if not isinstance(rejected, list):
        raise DiscoveryValidationError(
            "Invalid field: selection_reason.rejected_candidate_ids must be a list"
        )
    return {
        "summary": _normalize_optional_string(data.get("summary")),
        "deciding_factors": [
            _normalize_optional_string(item) for item in deciding if _normalize_optional_string(item)
        ],
        "evidence_ids": [
            _normalize_optional_string(item) for item in evidence_ids if _normalize_optional_string(item)
        ],
        "rejected_candidate_ids": [
            _normalize_optional_string(item) for item in rejected if _normalize_optional_string(item)
        ],
        "policy_applied": _normalize_optional_string(data.get("policy_applied")),
    }


def _normalize_manual_override(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid manual override at index {index}")
    return {
        "override_id": _require_non_empty_string(data, "override_id", path=f"manual_overrides[{index}]"),
        "resource_need_id": _require_non_empty_string(
            data, "resource_need_id", path=f"manual_overrides[{index}]"
        ),
        "previous_primary_id": _normalize_optional_string(data.get("previous_primary_id")) or None,
        "override_candidate_id": _require_non_empty_string(
            data, "override_candidate_id", path=f"manual_overrides[{index}]"
        ),
        "reason": _normalize_optional_string(data.get("reason")),
        "overridden_at": _normalize_optional_datetime(data.get("overridden_at")),
    }


def _normalize_discovery_gap(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid discovery gap at index {index}")
    examined = data.get("candidate_ids_examined", [])
    if examined is None:
        examined = []
    if not isinstance(examined, list):
        raise DiscoveryValidationError(f"Invalid candidate_ids_examined for gaps[{index}]")
    details = data.get("details", {})
    if details is None:
        details = {}
    if not isinstance(details, dict):
        raise DiscoveryValidationError(f"Invalid details for gaps[{index}]")
    return {
        "gap_id": _require_non_empty_string(data, "gap_id", path=f"discovery_gaps[{index}]"),
        "gap_type": _normalize_discovery_gap_type(
            data.get("gap_type"), path=f"discovery_gaps[{index}].gap_type"
        ),
        "severity": _normalize_gap_severity(
            data.get("severity"), path=f"discovery_gaps[{index}].severity"
        ),
        "resource_need_id": _normalize_optional_string(data.get("resource_need_id")) or None,
        "description": _require_non_empty_string(data, "description", path=f"discovery_gaps[{index}]"),
        "related_analysis_gap_index": data.get("related_analysis_gap_index"),
        "candidate_ids_examined": [
            _normalize_optional_string(item) for item in examined if _normalize_optional_string(item)
        ],
        "recommended_action": _normalize_recommended_action(data.get("recommended_action")),
        "details": {str(key): str(value) for key, value in details.items()},
    }


def _normalize_resource_need(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid resource need at index {index}")
    scopes = data.get("required_for_scope", [])
    if scopes is None:
        scopes = []
    if not isinstance(scopes, list):
        raise DiscoveryValidationError(f"Invalid required_for_scope for resource_need[{index}]")
    gap_index = data.get("analysis_gap_index")
    if gap_index is not None and not isinstance(gap_index, int):
        raise DiscoveryValidationError(f"Invalid analysis_gap_index for resource_need[{index}]")
    return {
        "need_id": _require_non_empty_string(data, "need_id", path=f"resource_need[{index}]"),
        "need_category": _normalize_need_category(
            data.get("need_category"), path=f"resource_need[{index}].need_category"
        ),
        "derived_from_analysis_gap": bool(data.get("derived_from_analysis_gap", False)),
        "analysis_gap_index": gap_index,
        "required_for_scope": [
            _normalize_optional_string(item) for item in scopes if _normalize_optional_string(item)
        ],
        "description": _normalize_optional_string(data.get("description")),
    }


def _normalize_gap_snapshot(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid analysis gap snapshot at index {index}")
    return {
        "category": _require_non_empty_string(data, "category", path=f"analysis_gaps_snapshot[{index}]"),
        "description": _require_non_empty_string(data, "description", path=f"analysis_gaps_snapshot[{index}]"),
    }


def _normalize_provider_record(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Invalid provider record at index {index}")
    return {
        "provider_name": _require_non_empty_string(data, "provider_name", path=f"providers_used[{index}]"),
        "provider_version": _normalize_optional_string(data.get("provider_version")),
        "invoked_at": _normalize_optional_datetime(data.get("invoked_at")),
        "status": _normalize_provider_invocation_status(data.get("status")),
        "candidates_contributed": _normalize_int(data.get("candidates_contributed"), default=0),
        "evidence_contributed": _normalize_int(data.get("evidence_contributed"), default=0),
        "error_summary": _normalize_optional_string(data.get("error_summary")) or None,
    }


def _candidate_list(data: dict) -> list[dict]:
    resources = data.get("candidate_resources", {})
    if not isinstance(resources, dict):
        return []
    candidates = resources.get("candidates", [])
    return candidates if isinstance(candidates, list) else []


def _evidence_list(data: dict) -> list[dict]:
    evidence = data.get("evidence", {})
    if not isinstance(evidence, dict):
        return []
    records = evidence.get("records", [])
    return records if isinstance(records, list) else []


def _verification_list(data: dict) -> list[dict]:
    verification = data.get("verification", {})
    if not isinstance(verification, dict):
        return []
    records = verification.get("records", [])
    return records if isinstance(records, list) else []


def _rank_list_list(data: dict) -> list[dict]:
    ranking = data.get("ranking", {})
    if not isinstance(ranking, dict):
        return []
    rank_lists = ranking.get("rank_lists", [])
    return rank_lists if isinstance(rank_lists, list) else []


def _selection_list(data: dict) -> list[dict]:
    selection = data.get("selection", {})
    if not isinstance(selection, dict):
        return []
    selections = selection.get("selections", [])
    return selections if isinstance(selections, list) else []


def _gap_list(data: dict) -> list[dict]:
    discovery_gaps = data.get("discovery_gaps", {})
    if not isinstance(discovery_gaps, dict):
        return []
    gaps = discovery_gaps.get("gaps", [])
    return gaps if isinstance(gaps, list) else []


def _validate_candidate_uniqueness(candidates: list[dict]) -> None:
    seen: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise DiscoveryValidationError(f"Invalid candidate at index {index}")
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise DiscoveryValidationError(f"Invalid candidate_id at index {index}")
        if candidate_id in seen:
            raise DiscoveryValidationError(f"Duplicate candidate_id: {candidate_id}")
        seen.add(candidate_id)


def _validate_reference_integrity(
    *,
    candidates: list[dict],
    evidence_records: list[dict],
    verification_records: list[dict],
    rank_lists: list[dict],
    selections: list[dict],
    gaps: list[dict],
) -> None:
    candidate_ids = {
        candidate["candidate_id"]
        for candidate in candidates
        if isinstance(candidate, dict) and isinstance(candidate.get("candidate_id"), str)
    }
    evidence_ids = {
        record["evidence_id"]
        for record in evidence_records
        if isinstance(record, dict) and isinstance(record.get("evidence_id"), str)
    }
    rank_list_ids = {
        rank_list["rank_list_id"]
        for rank_list in rank_lists
        if isinstance(rank_list, dict) and isinstance(rank_list.get("rank_list_id"), str)
    }

    for index, record in enumerate(evidence_records):
        if not isinstance(record, dict):
            continue
        candidate_id = record.get("candidate_id")
        if candidate_id not in candidate_ids:
            raise DiscoveryValidationError(
                f"evidence.records[{index}] references unknown candidate_id: {candidate_id}"
            )

    for index, record in enumerate(verification_records):
        if not isinstance(record, dict):
            continue
        candidate_id = record.get("candidate_id")
        if candidate_id not in candidate_ids:
            raise DiscoveryValidationError(
                f"verification.records[{index}] references unknown candidate_id: {candidate_id}"
            )
        for evidence_id in _dimension_evidence_ids(record):
            if evidence_id not in evidence_ids:
                raise DiscoveryValidationError(
                    f"verification.records[{index}] references unknown evidence_id: {evidence_id}"
                )

    for list_index, rank_list in enumerate(rank_lists):
        if not isinstance(rank_list, dict):
            continue
        for candidate_id in rank_list.get("ordered_candidate_ids", []):
            if candidate_id not in candidate_ids:
                raise DiscoveryValidationError(
                    f"ranking.rank_lists[{list_index}] references unknown candidate_id: {candidate_id}"
                )
        for candidate_id in rank_list.get("eligible_candidate_ids", []):
            if candidate_id not in candidate_ids:
                raise DiscoveryValidationError(
                    f"ranking.rank_lists[{list_index}] eligible list references unknown candidate_id: {candidate_id}"
                )

    for index, selection in enumerate(selections):
        if not isinstance(selection, dict):
            continue
        primary_id = selection.get("primary_candidate_id")
        if primary_id and primary_id not in candidate_ids:
            raise DiscoveryValidationError(
                f"selection.selections[{index}] references unknown primary_candidate_id: {primary_id}"
            )
        for candidate_id in selection.get("fallback_candidate_ids", []):
            if candidate_id not in candidate_ids:
                raise DiscoveryValidationError(
                    f"selection.selections[{index}] references unknown fallback candidate_id: {candidate_id}"
                )
        rank_list_id = selection.get("rank_list_id")
        if rank_list_id and rank_list_id not in rank_list_ids:
            raise DiscoveryValidationError(
                f"selection.selections[{index}] references unknown rank_list_id: {rank_list_id}"
            )
        for evidence_id in _selection_reason_evidence_ids(selection):
            if evidence_id not in evidence_ids:
                raise DiscoveryValidationError(
                    f"selection.selections[{index}] references unknown evidence_id: {evidence_id}"
                )

    for index, gap in enumerate(gaps):
        if not isinstance(gap, dict):
            continue
        for candidate_id in gap.get("candidate_ids_examined", []):
            if candidate_id not in candidate_ids:
                raise DiscoveryValidationError(
                    f"discovery_gaps.gaps[{index}] references unknown candidate_id: {candidate_id}"
                )


def _validate_metadata_counts(
    metadata: dict,
    candidates: list[dict],
    selections: list[dict],
    gaps: list[dict],
) -> None:
    candidate_count = metadata.get("candidate_count")
    if isinstance(candidate_count, int) and candidate_count != len(candidates):
        raise DiscoveryValidationError("metadata.candidate_count does not match candidate list length")
    selection_count = metadata.get("selection_count")
    if isinstance(selection_count, int):
        primary_count = sum(
            1
            for selection in selections
            if isinstance(selection, dict) and selection.get("primary_candidate_id")
        )
        if selection_count != primary_count:
            raise DiscoveryValidationError("metadata.selection_count does not match primary selections")
    unresolved_gap_count = metadata.get("unresolved_gap_count")
    if isinstance(unresolved_gap_count, int) and unresolved_gap_count != len(gaps):
        raise DiscoveryValidationError("metadata.unresolved_gap_count does not match discovery gap count")


def _validate_selection_records(
    selections: list[dict],
    candidates: list[dict],
    verification_records: list[dict],
    rank_lists: list[dict],
) -> None:
    verification_by_candidate = {
        record.get("candidate_id"): record.get("status")
        for record in verification_records
        if isinstance(record, dict)
    }
    for index, selection in enumerate(selections):
        if not isinstance(selection, dict):
            continue
        primary_id = selection.get("primary_candidate_id")
        if not primary_id:
            continue
        status = verification_by_candidate.get(primary_id)
        if status is not None:
            normalized = _normalize_verification_status(status, path="selection verification")
            if normalized not in _ALLOWED_SELECTION_VERIFICATION:
                raise DiscoveryValidationError(
                    f"selection.selections[{index}] primary candidate has invalid verification status"
                )
        for fallback_id in selection.get("fallback_candidate_ids", []):
            status = verification_by_candidate.get(fallback_id)
            if status is not None:
                normalized = _normalize_verification_status(status, path="selection verification")
                if normalized not in _ALLOWED_SELECTION_VERIFICATION:
                    raise DiscoveryValidationError(
                        f"selection.selections[{index}] fallback candidate has invalid verification status"
                    )
    del rank_lists


def _validate_gap_records(gaps: list[dict]) -> None:
    seen: set[str] = set()
    for index, gap in enumerate(gaps):
        if not isinstance(gap, dict):
            raise DiscoveryValidationError(f"Invalid discovery gap at index {index}")
        gap_id = gap.get("gap_id")
        if not isinstance(gap_id, str) or not gap_id.strip():
            raise DiscoveryValidationError(f"Invalid gap_id at index {index}")
        if gap_id in seen:
            raise DiscoveryValidationError(f"Duplicate gap_id: {gap_id}")
        seen.add(gap_id)
        _require_non_empty_string(gap, "description", path=f"discovery_gaps[{index}]")


def _dimension_evidence_ids(record: dict) -> list[str]:
    evidence_ids: list[str] = []
    for dimension in record.get("dimensions", []):
        if isinstance(dimension, dict):
            for evidence_id in dimension.get("evidence_ids", []):
                if isinstance(evidence_id, str):
                    evidence_ids.append(evidence_id)
    return evidence_ids


def _selection_reason_evidence_ids(selection: dict) -> list[str]:
    reason = selection.get("selection_reason", {})
    if not isinstance(reason, dict):
        return []
    return [
        evidence_id
        for evidence_id in reason.get("evidence_ids", [])
        if isinstance(evidence_id, str)
    ]


def _validate_schema_version(value: object) -> None:
    _normalize_schema_version(value)


def _normalize_schema_version(value: object) -> str:
    if value is None or value == "":
        return SCHEMA_VERSION
    if not isinstance(value, str):
        raise DiscoveryValidationError("Invalid field: schema_version must be a string")
    stripped = value.strip()
    if not stripped:
        raise DiscoveryValidationError("Invalid field: schema_version must be non-empty")
    return stripped


def _normalize_enum(value: object, enum_cls, *, path: str, default=None):
    if value is None or value == "":
        if default is not None:
            return default
        raise DiscoveryValidationError(f"Invalid field: {path}")
    if isinstance(value, enum_cls):
        return value
    if not isinstance(value, str):
        raise DiscoveryValidationError(f"Invalid field: {path}")
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    for item in enum_cls:
        if item.value == normalized:
            return item
    raise DiscoveryValidationError(f"Invalid value for {path}: {value!r}")


def _normalize_discovery_status(value: object, *, path: str) -> DiscoveryStatus:
    return _normalize_enum(value, DiscoveryStatus, path=path)


def _validate_discovery_status(value: object, *, path: str) -> None:
    if value is None or value == "":
        raise DiscoveryValidationError(f"Missing required field: {path}")
    _normalize_discovery_status(value, path=path)


def _normalize_invocation_reason(value: object, *, path: str) -> InvocationReason:
    return _normalize_enum(
        value, InvocationReason, path=path, default=InvocationReason.GAP_TRIGGERED
    )


def _validate_invocation_reason(value: object, *, path: str) -> None:
    if value is None or value == "":
        return
    _normalize_invocation_reason(value, path=path)


def _normalize_discovery_provider(value: object, *, path: str) -> DiscoveryProvider:
    return _normalize_enum(value, DiscoveryProvider, path=path)


def _normalize_resource_type(value: object, *, path: str) -> ResourceType:
    return _normalize_enum(value, ResourceType, path=path)


def _normalize_officiality(value: object, *, path: str) -> Officiality:
    return _normalize_enum(value, Officiality, path=path, default=Officiality.UNKNOWN)


def _normalize_candidate_status(value: object, *, path: str) -> CandidateStatus:
    return _normalize_enum(value, CandidateStatus, path=path, default=CandidateStatus.COLLECTED)


def _normalize_paper_relation_type(value: object) -> PaperRelationType:
    return _normalize_enum(value, PaperRelationType, path="paper_relation.relation_type", default=PaperRelationType.NONE)


def _normalize_relation_strength(value: object) -> RelationStrength:
    return _normalize_enum(value, RelationStrength, path="paper_relation.relation_strength", default=RelationStrength.WEAK)


def _normalize_collection_source_type(value: object, *, path: str) -> CollectionSourceType:
    return _normalize_enum(value, CollectionSourceType, path=path)


def _normalize_evidence_type(value: object, *, path: str) -> EvidenceType:
    return _normalize_enum(value, EvidenceType, path=path)


def _normalize_evidence_polarity(value: object) -> EvidencePolarity:
    return _normalize_enum(value, EvidencePolarity, path="evidence.polarity", default=EvidencePolarity.NEUTRAL)


def _normalize_evidence_source_kind(value: object, *, path: str) -> EvidenceSourceKind:
    return _normalize_enum(value, EvidenceSourceKind, path=path)


def _normalize_fetch_status(value: object) -> FetchStatus:
    return _normalize_enum(value, FetchStatus, path="evidence_source.fetch_status", default=FetchStatus.SUCCESS)


def _normalize_verification_status(value: object, *, path: str) -> VerificationStatus:
    return _normalize_enum(value, VerificationStatus, path=path)


def _normalize_verification_dimension_name(value: object) -> VerificationDimensionName:
    return _normalize_enum(value, VerificationDimensionName, path="verification.dimension")


def _normalize_dimension_result(value: object) -> DimensionResult:
    return _normalize_enum(value, DimensionResult, path="verification.dimension.result")


def _normalize_need_category(value: object, *, path: str) -> NeedCategory:
    return _normalize_enum(value, NeedCategory, path=path)


def _normalize_discovery_gap_type(value: object, *, path: str) -> DiscoveryGapType:
    return _normalize_enum(value, DiscoveryGapType, path=path)


def _normalize_gap_severity(value: object, *, path: str) -> GapSeverity:
    return _normalize_enum(value, GapSeverity, path=path)


def _normalize_recommended_action(value: object) -> RecommendedAction:
    return _normalize_enum(
        value, RecommendedAction, path="discovery_gap.recommended_action", default=RecommendedAction.MANUAL_INPUT
    )


def _normalize_provider_invocation_status(value: object) -> ProviderInvocationStatus:
    return _normalize_enum(
        value,
        ProviderInvocationStatus,
        path="provider.status",
        default=ProviderInvocationStatus.SKIPPED,
    )


def _require_dict(data: dict, field: str) -> None:
    if field not in data or not isinstance(data[field], dict):
        raise DiscoveryValidationError(f"Missing required field: {field}")


def _require_dict_instance(data: dict, path: str) -> None:
    if not isinstance(data, dict):
        raise DiscoveryValidationError(f"Missing required field: {path}")


def _require_non_empty_string(data: dict, field: str, *, path: str) -> str:
    if field not in data:
        raise DiscoveryValidationError(f"Missing required field: {path}.{field}")
    value = data[field]
    if not isinstance(value, str):
        raise DiscoveryValidationError(f"Invalid required field: {path}.{field}")
    stripped = value.strip()
    if not stripped:
        raise DiscoveryValidationError(f"Invalid required field: {path}.{field}")
    return stripped


def _normalize_optional_string(value: object, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        return str(value).strip()
    return value.strip()


def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DiscoveryValidationError("Expected a list of strings")
    return [_normalize_optional_string(item) for item in value if _normalize_optional_string(item)]


def _normalize_int(value: object, *, default: int) -> int:
    if value is None or value == "":
        return default
    if not isinstance(value, int):
        raise DiscoveryValidationError("Expected an integer")
    return value


def _normalize_float(value: object, *, default: float) -> float:
    if value is None or value == "":
        return default
    if not isinstance(value, (int, float)):
        raise DiscoveryValidationError("Expected a float")
    return float(value)


def _normalize_datetime(value: object, *, path: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryValidationError(f"Invalid datetime field: {path}")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise DiscoveryValidationError(f"Invalid datetime field: {path}") from exc


def _normalize_optional_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    return _normalize_datetime(value, path="datetime")
