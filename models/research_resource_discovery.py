from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


class DiscoveryStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class InvocationReason(str, Enum):
    GAP_TRIGGERED = "gap_triggered"
    USER_REQUESTED = "user_requested"
    POLICY_MANDATORY = "policy_mandatory"
    MANUAL_RERUN = "manual_rerun"


class ResourceType(str, Enum):
    OFFICIAL_REPOSITORY = "official_repository"
    COMMUNITY_REPOSITORY = "community_repository"
    PROJECT_PAGE = "project_page"
    CHECKPOINT = "checkpoint"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    DATASET_PORTAL = "dataset_portal"
    MODEL_CARD = "model_card"
    HUGGINGFACE_MODEL = "huggingface_model"
    HUGGINGFACE_DATASET = "huggingface_dataset"
    DOCKER_IMAGE = "docker_image"
    RELEASE_ASSET = "release_asset"
    ZENODO_RECORD = "zenodo_record"
    FIGSHARE_DATASET = "figshare_dataset"
    PAPERS_WITH_CODE_ENTRY = "papers_with_code_entry"
    PYPI_PACKAGE = "pypi_package"
    CONDA_PACKAGE = "conda_package"
    COLAB_NOTEBOOK = "colab_notebook"
    INSTITUTIONAL_MIRROR = "institutional_mirror"
    CUSTOM = "custom"


class DiscoveryProvider(str, Enum):
    PAPER_LINK = "paper_link"
    GITHUB = "github"
    GITLAB = "gitlab"
    HUGGINGFACE = "huggingface"
    HTTP = "http"
    OPENALEX = "openalex"
    CROSSREF = "crossref"
    PAPERS_WITH_CODE = "papers_with_code"
    MANUAL = "manual"
    OTHER = "other"


class Officiality(str, Enum):
    OFFICIAL = "official"
    AUTHOR_AFFILIATED = "author_affiliated"
    COMMUNITY = "community"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


class CandidateStatus(str, Enum):
    COLLECTED = "collected"
    EVIDENCE_PENDING = "evidence_pending"
    EVIDENCE_COMPLETE = "evidence_complete"
    VERIFIED = "verified"
    RANKED = "ranked"
    SELECTED_PRIMARY = "selected_primary"
    SELECTED_FALLBACK = "selected_fallback"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class PaperRelationType(str, Enum):
    CITED_IN_PAPER = "cited_in_paper"
    SAME_AUTHORS = "same_authors"
    SAME_ARXIV = "same_arxiv"
    SAME_TITLE = "same_title"
    LINKED_FROM_PROJECT_PAGE = "linked_from_project_page"
    INDEX_MATCH = "index_match"
    INFERRED = "inferred"
    NONE = "none"


class RelationStrength(str, Enum):
    EXPLICIT = "explicit"
    STRONG = "strong"
    WEAK = "weak"
    SPECULATIVE = "speculative"


class CollectionSourceType(str, Enum):
    ANALYSIS_EXTERNAL_RESOURCE = "analysis_external_resource"
    ANALYSIS_ARTIFACT = "analysis_artifact"
    ANALYSIS_DATASET_LINK = "analysis_dataset_link"
    METADATA_LOOKUP = "metadata_lookup"
    PROVIDER_SEARCH = "provider_search"
    PROVIDER_GRAPH = "provider_graph"
    CROSS_REFERENCE = "cross_reference"
    MANUAL = "manual"


class EvidenceType(str, Enum):
    PAPER_CITATION_MATCH = "paper_citation_match"
    TITLE_MATCH = "title_match"
    AUTHOR_MATCH = "author_match"
    FILE_PRESENCE = "file_presence"
    DIRECTORY_STRUCTURE = "directory_structure"
    LICENSE_PRESENT = "license_present"
    LICENSE_TYPE = "license_type"
    README_CLAIM = "readme_claim"
    COMMIT_RECENCY = "commit_recency"
    STAR_COUNT = "star_count"
    FORK_OF = "fork_of"
    MODEL_CARD_FIELD = "model_card_field"
    HTTP_STATUS = "http_status"
    REDIRECT_CHAIN = "redirect_chain"
    METADATA_EXTRACT = "metadata_extract"
    CROSS_REFERENCE = "cross_reference"
    EMBEDDED_REFERENCE = "embedded_reference"
    OTHER = "other"


class EvidencePolarity(str, Enum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    NEUTRAL = "neutral"


class EvidenceSourceKind(str, Enum):
    HTTP_FETCH = "http_fetch"
    PROVIDER_API = "provider_api"
    PAPER_TEXT = "paper_text"
    ANALYSIS_FIELD = "analysis_field"
    HTML_PARSE = "html_parse"
    LLM_EXTRACT = "llm_extract"


class FetchStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class VerificationStatus(str, Enum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    SKIPPED = "skipped"
    ERROR = "error"


class VerificationDimensionName(str, Enum):
    IDENTITY_MATCH = "identity_match"
    PAPER_MATCH = "paper_match"
    FRAMEWORK_MATCH = "framework_match"
    LICENSE = "license"
    REPOSITORY_HEALTH = "repository_health"
    ARTIFACT_AVAILABILITY = "artifact_availability"
    VERSION_ALIGNMENT = "version_alignment"
    SCOPE_ALIGNMENT = "scope_alignment"


class DimensionResult(str, Enum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class NeedCategory(str, Enum):
    CODE_REPOSITORY = "code_repository"
    CHECKPOINT = "checkpoint"
    DATASET = "dataset"
    CONFIG = "config"
    DOCUMENTATION = "documentation"
    PROJECT_HOME = "project_home"
    EVALUATION_ASSET = "evaluation_asset"


class DiscoveryGapType(str, Enum):
    NO_OFFICIAL_REPOSITORY = "no_official_repository"
    NO_VIABLE_REPOSITORY = "no_viable_repository"
    CHECKPOINT_MISSING = "checkpoint_missing"
    CONFIG_MISSING = "config_missing"
    DATASET_UNAVAILABLE = "dataset_unavailable"
    REPOSITORY_ARCHIVED = "repository_archived"
    FRAMEWORK_MISMATCH = "framework_mismatch"
    LICENSE_BLOCKED = "license_blocked"
    SCOPE_INSUFFICIENT = "scope_insufficient"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    AMBIGUOUS_MULTIPLE_OFFICIAL = "ambiguous_multiple_official"
    PAPER_LINK_DEAD = "paper_link_dead"
    OTHER = "other"


class GapSeverity(str, Enum):
    BLOCKING = "blocking"
    DEGRADED = "degraded"
    INFORMATIONAL = "informational"


class RecommendedAction(str, Enum):
    GENERATE_FROM_SCRATCH = "generate_from_scratch"
    MANUAL_INPUT = "manual_input"
    NARROW_SCOPE = "narrow_scope"
    RETRY_DISCOVERY = "retry_discovery"
    ABORT = "abort"
    PROCEED_WITH_PARTIAL = "proceed_with_partial"


class ProviderInvocationStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class DiscoveryMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    discovery_id: str
    created_at: datetime
    status: DiscoveryStatus
    summary: str = ""
    reproduction_scope: str = "unknown"
    invocation_reason: InvocationReason = InvocationReason.GAP_TRIGGERED
    candidate_count: int = 0
    selection_count: int = 0
    unresolved_gap_count: int = 0


class ProviderRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_name: str
    provider_version: str = ""
    invoked_at: datetime | None = None
    status: ProviderInvocationStatus = ProviderInvocationStatus.SKIPPED
    candidates_contributed: int = 0
    evidence_contributed: int = 0
    error_summary: str | None = None


class DiscoveryProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    discovery_run_id: str = ""
    pipeline_version: str = ""
    stage_timestamps: dict[str, datetime] = Field(default_factory=dict)
    providers_used: list[ProviderRecord] = Field(default_factory=list)
    degradation_notes: list[str] = Field(default_factory=list)
    configuration_fingerprint: str = ""
    rerun_of: str | None = None


class AnalysisGapSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    description: str


class AnalysisReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysis_schema_version: str
    paper_title: str
    arxiv_id: str = ""
    source_path: str | None = None
    analysis_content_hash: str
    analysis_gaps_addressed: list[str] = Field(default_factory=list)
    analysis_gaps_snapshot: list[AnalysisGapSnapshot] = Field(default_factory=list)


class ResourceIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: DiscoveryProvider
    provider_native_id: str = ""
    normalized_url: str = ""
    content_hash: str | None = None


class PaperRelation(BaseModel):
    model_config = ConfigDict(frozen=True)

    relation_type: PaperRelationType = PaperRelationType.NONE
    relation_strength: RelationStrength = RelationStrength.WEAK
    matching_signals: list[str] = Field(default_factory=list)


class CollectionSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_type: CollectionSourceType
    provider_name: str | None = None
    source_query: str | None = None
    seed_candidate_id: str | None = None


class ResourceNeed(BaseModel):
    model_config = ConfigDict(frozen=True)

    need_id: str
    need_category: NeedCategory
    derived_from_analysis_gap: bool = False
    analysis_gap_index: int | None = None
    required_for_scope: list[str] = Field(default_factory=list)
    description: str = ""


class RepositoryCandidate(BaseModel):
    """Canonical candidate resource (schema: Candidate)."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str
    identity: ResourceIdentity
    provider: DiscoveryProvider
    resource_type: ResourceType
    tier: int = 1
    url: str = ""
    title: str = ""
    officiality: Officiality = Officiality.UNKNOWN
    paper_relation: PaperRelation = Field(default_factory=PaperRelation)
    collection_source: CollectionSource
    status: CandidateStatus = CandidateStatus.COLLECTED
    confidence: float = 0.0
    related_candidate_ids: list[str] = Field(default_factory=list)
    addresses_needs: list[str] = Field(default_factory=list)
    notes: str = ""
    collected_at: datetime | None = None
    extensions: dict[str, str] = Field(default_factory=dict)
    custom_type_label: str | None = None


class CandidateResources(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: list[RepositoryCandidate] = Field(default_factory=list)
    indexes: dict[str, list[str]] = Field(default_factory=dict)


class EvidenceSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_kind: EvidenceSourceKind
    provider_name: str | None = None
    uri: str = ""
    fetch_status: FetchStatus = FetchStatus.SUCCESS


class ObservedFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    fields: dict[str, str | int | float | bool] = Field(default_factory=dict)
    custom_type_label: str | None = None
    extensions: dict[str, str] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    candidate_id: str
    evidence_type: EvidenceType
    evidence_source: EvidenceSource
    observed_fact: ObservedFact = Field(default_factory=ObservedFact)
    polarity: EvidencePolarity = EvidencePolarity.NEUTRAL
    confidence: float = 0.0
    collected_at: datetime | None = None
    expires_at: datetime | None = None
    raw_reference: str | None = None
    custom_type_label: str | None = None


class EvidenceCollection(BaseModel):
    model_config = ConfigDict(frozen=True)

    records: list[EvidenceRecord] = Field(default_factory=list)
    indexes: dict[str, list[str]] = Field(default_factory=dict)


class VerificationDimension(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: VerificationDimensionName
    result: DimensionResult
    summary: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)


class VerificationRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_id: str
    candidate_id: str
    status: VerificationStatus
    dimensions: list[VerificationDimension] = Field(default_factory=list)
    blocking_failures: list[str] = Field(default_factory=list)
    verified_at: datetime | None = None
    verifier_version: str = ""


class VerificationCollection(BaseModel):
    model_config = ConfigDict(frozen=True)

    records: list[VerificationRecord] = Field(default_factory=list)
    indexes: dict[str, list[str]] = Field(default_factory=dict)


class RankingFactor(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    score: float = 0.0
    weight: float = 0.0
    summary: str = ""


class RankScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    total_score: float = 0.0
    factor_scores: dict[str, float] = Field(default_factory=dict)
    ranking_factors: list[RankingFactor] = Field(default_factory=list)


class RankList(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank_list_id: str
    resource_need: ResourceNeed
    ordered_candidate_ids: list[str] = Field(default_factory=list)
    scores: dict[str, RankScore] = Field(default_factory=dict)
    ranking_factors_summary: str = ""
    eligible_candidate_ids: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class RankingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank_lists: list[RankList] = Field(default_factory=list)
    global_notes: str = ""


class SelectionReason(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: str = ""
    deciding_factors: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    rejected_candidate_ids: list[str] = Field(default_factory=list)
    policy_applied: str = ""


class SelectionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    selection_id: str
    resource_need: ResourceNeed
    primary_candidate_id: str | None = None
    fallback_candidate_ids: list[str] = Field(default_factory=list)
    selection_reason: SelectionReason = Field(default_factory=SelectionReason)
    confidence: float = 0.0
    selected_at: datetime | None = None
    rank_list_id: str = ""
    verification_snapshot: dict[str, str] = Field(default_factory=dict)


class ManualOverride(BaseModel):
    model_config = ConfigDict(frozen=True)

    override_id: str
    resource_need_id: str
    previous_primary_id: str | None = None
    override_candidate_id: str
    reason: str = ""
    overridden_at: datetime | None = None


class SelectionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    selections: list[SelectionRecord] = Field(default_factory=list)
    retained_candidate_policy: str = "full_candidate_set_preserved"
    manual_overrides: list[ManualOverride] = Field(default_factory=list)


class DiscoveryGap(BaseModel):
    model_config = ConfigDict(frozen=True)

    gap_id: str
    gap_type: DiscoveryGapType
    severity: GapSeverity
    resource_need_id: str | None = None
    description: str
    related_analysis_gap_index: int | None = None
    candidate_ids_examined: list[str] = Field(default_factory=list)
    recommended_action: RecommendedAction = RecommendedAction.MANUAL_INPUT
    details: dict[str, str] = Field(default_factory=dict)


class DiscoveryGaps(BaseModel):
    model_config = ConfigDict(frozen=True)

    gaps: list[DiscoveryGap] = Field(default_factory=list)
    analysis_gaps_closed: list[str] = Field(default_factory=list)
    analysis_gaps_remaining: list[str] = Field(default_factory=list)


class DiscoveryStatistics(BaseModel):
    """Denormalized counts mirrored in metadata for convenience."""

    model_config = ConfigDict(frozen=True)

    candidate_count: int = 0
    selection_count: int = 0
    unresolved_gap_count: int = 0
    evidence_count: int = 0
    verification_count: int = 0


class ResearchResourceDiscovery(BaseModel):
    model_config = ConfigDict(frozen=True)

    metadata: DiscoveryMetadata
    provenance: DiscoveryProvenance = Field(default_factory=DiscoveryProvenance)
    analysis_reference: AnalysisReference
    candidate_resources: CandidateResources = Field(default_factory=CandidateResources)
    evidence: EvidenceCollection = Field(default_factory=EvidenceCollection)
    verification: VerificationCollection = Field(default_factory=VerificationCollection)
    ranking: RankingResult = Field(default_factory=RankingResult)
    selection: SelectionResult = Field(default_factory=SelectionResult)
    discovery_gaps: DiscoveryGaps = Field(default_factory=DiscoveryGaps)
    statistics: DiscoveryStatistics = Field(default_factory=DiscoveryStatistics)
    schema_version: str = SCHEMA_VERSION
