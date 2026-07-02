from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from models.research_resource_discovery import DiscoveryStatus

SCHEMA_VERSION = "1.0"


class PlanningStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    MANUAL_REVIEW = "manual_review"
    ABORTED = "aborted"


class PlanningInvocationReason(str, Enum):
    DISCOVERY_COMPLETE = "discovery_complete"
    DISCOVERY_PARTIAL = "discovery_partial"
    USER_REQUESTED = "user_requested"
    POLICY_MANDATORY = "policy_mandatory"
    MANUAL_RERUN = "manual_rerun"


class StrategyPosture(str, Enum):
    OFFICIAL_REPOSITORY = "official_repository"
    COMMUNITY_FORK = "community_fork"
    HYBRID = "hybrid"
    GREENFIELD = "greenfield"
    MANUAL = "manual"


class ScopeCommitment(str, Enum):
    FULL_REPRODUCTION = "full_reproduction"
    PARTIAL_REPRODUCTION = "partial_reproduction"
    NARROWED_SCOPE = "narrowed_scope"
    EVAL_ONLY = "eval_only"
    INFERENCE_ONLY = "inference_only"


class BindingRole(str, Enum):
    PRIMARY_REPOSITORY = "primary_repository"
    FALLBACK_REPOSITORY = "fallback_repository"
    CHECKPOINT = "checkpoint"
    DATASET = "dataset"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    PROJECT_HOME = "project_home"
    SUPPORTING_ASSET = "supporting_asset"


class UsageIntent(str, Enum):
    EXECUTE_DIRECTLY = "execute_directly"
    EXTRACT_ASSETS_FROM = "extract_assets_from"
    REFERENCE_ONLY = "reference_only"
    FALLBACK_IF_PRIMARY_FAILS = "fallback_if_primary_fails"


class ReuseMode(str, Enum):
    AS_IS = "as_is"
    FORK_BASED = "fork_based"
    HYBRID_COMPONENTS = "hybrid_components"
    NOT_APPLICABLE = "not_applicable"


class ReuseExtent(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    ENTRYPOINT_ONLY = "entrypoint_only"


class AdaptationScope(str, Enum):
    NONE = "none"
    MINIMAL = "minimal"
    MODERATE = "moderate"
    EXTENSIVE = "extensive"


class ModificationClass(str, Enum):
    DEPENDENCY_PIN = "dependency_pin"
    CONFIG_PATCH = "config_patch"
    SCRIPT_PATCH = "script_patch"
    FORK = "fork"
    FRAMEWORK_PORT = "framework_port"


class AuthorizationLevel(str, Enum):
    PLANNER_TASK = "planner_task"
    CODER_DISCRETION = "coder_discretion"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"


class AdaptationTriggerType(str, Enum):
    DISCOVERY_GAP = "discovery_gap"
    VERIFICATION_PARTIAL = "verification_partial"
    SCOPE_MISMATCH = "scope_mismatch"
    FRAMEWORK_VERSION = "framework_version"


class GenerationScope(str, Enum):
    NONE = "none"
    FULL_CODEBASE = "full_codebase"
    MISSING_MODULES = "missing_modules"
    CONFIG_AND_SCRIPTS = "config_and_scripts"
    EVAL_HARNESS_ONLY = "eval_harness_only"
    DOCUMENTATION_ONLY = "documentation_only"


class AnalysisModule(str, Enum):
    METHOD = "method"
    EVALUATION = "evaluation"
    RESOURCES = "resources"
    GOAL = "goal"


class GenerationIntent(str, Enum):
    IMPLEMENT_FROM_PAPER = "implement_from_paper"
    STUB_FOR_INTEGRATION = "stub_for_integration"
    REPLACE_MISSING_UPSTREAM = "replace_missing_upstream"


class GenerationPriority(str, Enum):
    BLOCKING = "blocking"
    DEGRADED = "degraded"
    OPTIONAL = "optional"


class RiskSeverity(str, Enum):
    BLOCKING = "blocking"
    DEGRADED = "degraded"
    INFORMATIONAL = "informational"


class RiskCategory(str, Enum):
    UNRESOLVED_RESOURCE = "unresolved_resource"
    VERIFICATION_LOW_CONFIDENCE = "verification_low_confidence"
    LICENSE = "license"
    SCOPE_MISMATCH = "scope_mismatch"
    AMBIGUOUS_OFFICIAL = "ambiguous_official"
    OTHER = "other"


class DecisionCategory(str, Enum):
    RESOURCE = "resource"
    REUSE = "reuse"
    ADAPTATION = "adaptation"
    GENERATION = "generation"
    RISK = "risk"


class StrategyMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str = Field(description="Unique ID for this planning run.")
    created_at: datetime = Field(description="When Execution Planning completed.")
    status: PlanningStatus = Field(description="Overall planning outcome status.")
    summary: str = Field(default="", description="Human-readable one-line outcome.")
    reproduction_scope: str = Field(
        default="unknown",
        description="Snapshot of goal.scope from analysis at planning time.",
    )
    invocation_reason: PlanningInvocationReason = Field(
        default=PlanningInvocationReason.DISCOVERY_COMPLETE,
        description="Why Execution Planning ran.",
    )
    strategy_posture: StrategyPosture = Field(
        default=StrategyPosture.MANUAL,
        description="Denormalized copy of strategy.primary_posture for quick filtering.",
    )
    binding_count: int = Field(default=0, description="Number of active resource bindings.")
    blocking_risk_count: int = Field(
        default=0,
        description="Count of risk_assessment.blocking_risks.",
    )
    manual_action_required: bool = Field(
        default=False,
        description="True when posture is manual or risks require human input.",
    )


class AnalysisReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysis_schema_version: str = Field(
        description="PaperReproductionAnalysis.schema_version at input time.",
    )
    paper_title: str = Field(description="Denormalized paper title for display and audit.")
    arxiv_id: str = Field(default="", description="Denormalized arXiv ID; empty if absent.")
    analysis_content_hash: str = Field(
        description="Hash of canonical analysis serialization.",
    )
    reproduction_scope: str = Field(
        default="unknown",
        description="Snapshot of goal.scope at planning time.",
    )
    analysis_gap_categories: list[str] = Field(
        default_factory=list,
        description="Gap category values at planning time — not full gap objects.",
    )


class DiscoveryReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    discovery_schema_version: str = Field(
        description="ResearchResourceDiscovery.schema_version at input time.",
    )
    discovery_id: str = Field(description="metadata.discovery_id of input artifact.")
    discovery_content_hash: str = Field(
        description="Hash of canonical discovery serialization.",
    )
    discovery_status: DiscoveryStatus = Field(
        description="Discovery metadata.status snapshot at input time.",
    )
    selection_ids_used: list[str] = Field(
        default_factory=list,
        description="selection_id values referenced by resource_bindings.",
    )
    unresolved_discovery_gap_count: int = Field(
        default=0,
        description="Snapshot of unresolved discovery gaps at planning time.",
    )


class InputReferences(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysis_reference: AnalysisReference
    discovery_reference: DiscoveryReference


class RejectedPosture(BaseModel):
    model_config = ConfigDict(frozen=True)

    posture: StrategyPosture = Field(description="Posture that was not selected.")
    rejection_reason: str = Field(default="", description="Short explanation for rejection.")
    related_discovery_gap_id: str | None = Field(
        default=None,
        description="Optional discovery gap reference motivating rejection.",
    )


class Strategy(BaseModel):
    model_config = ConfigDict(frozen=True)

    primary_posture: StrategyPosture = Field(description="Committed engineering posture.")
    scope_commitment: ScopeCommitment = Field(
        default=ScopeCommitment.FULL_REPRODUCTION,
        description="Committed reproduction scope.",
    )
    scope_narrowing_rationale: str | None = Field(
        default=None,
        description="Required when scope_commitment is narrowed.",
    )
    rationale: str = Field(default="", description="Primary human-readable strategy explanation.")
    deciding_factors: list[str] = Field(
        default_factory=list,
        description="Named factors that informed the strategy decision.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall strategy confidence.",
    )
    alternative_postures_rejected: list[RejectedPosture] = Field(
        default_factory=list,
        description="Postures considered and rejected for audit.",
    )


class ResourceBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    binding_id: str = Field(description="Unique binding ID within ExecutionStrategy.")
    candidate_id: str = Field(
        description="Reference to ResearchResourceDiscovery candidate_resources.candidates.",
    )
    selection_id: str | None = Field(
        default=None,
        description="Reference to discovery selection.selection_id when applicable.",
    )
    resource_need_id: str | None = Field(
        default=None,
        description="Reference to discovery resource need satisfied.",
    )
    role: BindingRole = Field(description="Role of this resource in the campaign.")
    usage_intent: UsageIntent = Field(
        default=UsageIntent.EXECUTE_DIRECTLY,
        description="How this bound resource will be used.",
    )
    binding_rationale: str = Field(
        default="",
        description="Why this candidate was bound for this role.",
    )
    overrides_discovery_selection: bool = Field(
        default=False,
        description="True when binding a non-primary discovery selection.",
    )
    override_rationale: str | None = Field(
        default=None,
        description="Required when overrides_discovery_selection is true.",
    )


class ResourceBindings(BaseModel):
    model_config = ConfigDict(frozen=True)

    bindings: list[ResourceBinding] = Field(
        default_factory=list,
        description="Active resource bindings for this campaign.",
    )
    anchor_binding_id: str | None = Field(
        default=None,
        description="Binding ID that anchors the workspace.",
    )
    combination_rationale: str = Field(
        default="",
        description="Why this resource set forms a coherent reproduction path.",
    )


class ReuseComponent(BaseModel):
    model_config = ConfigDict(frozen=True)

    binding_id: str = Field(description="Reference to resource_bindings.binding_id.")
    component_label: str = Field(
        default="",
        description="Logical component label such as training_code or weights.",
    )
    reuse_extent: ReuseExtent = Field(
        default=ReuseExtent.FULL,
        description="Extent of reuse for this component.",
    )


class ExcludedComponent(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(description="Discovery candidate reference.")
    exclusion_reason: str = Field(
        default="",
        description="Why the candidate was not reused despite discovery.",
    )


class ReusePlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    reuse_mode: ReuseMode = Field(
        default=ReuseMode.NOT_APPLICABLE,
        description="Committed reuse mode for the campaign.",
    )
    primary_reuse_binding_id: str | None = Field(
        default=None,
        description="Main reuse target binding reference.",
    )
    components_to_reuse: list[ReuseComponent] = Field(
        default_factory=list,
        description="Resources or logical components committed to reuse.",
    )
    components_excluded: list[ExcludedComponent] = Field(
        default_factory=list,
        description="Discovered resources explicitly not reused.",
    )
    reuse_assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions reuse depends on.",
    )
    reuse_limitations: list[str] = Field(
        default_factory=list,
        description="Known limitations accepted with reuse.",
    )


class AuthorizedModification(BaseModel):
    model_config = ConfigDict(frozen=True)

    modification_class: ModificationClass = Field(
        description="Permitted modification class.",
    )
    target_binding_id: str | None = Field(
        default=None,
        description="Optional binding reference for the modification.",
    )
    authorization_level: AuthorizationLevel = Field(
        default=AuthorizationLevel.PLANNER_TASK,
        description="Who may apply this modification class.",
    )


class AdaptationTrigger(BaseModel):
    model_config = ConfigDict(frozen=True)

    trigger_type: AdaptationTriggerType = Field(description="Why adaptation is needed.")
    description: str = Field(default="", description="Human-readable trigger description.")
    related_discovery_gap_id: str | None = Field(
        default=None,
        description="Optional discovery gap reference.",
    )


class AdaptationPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    adaptation_required: bool = Field(
        default=False,
        description="Whether downstream Repository Adaptation is expected.",
    )
    adaptation_scope: AdaptationScope = Field(
        default=AdaptationScope.NONE,
        description="Authorized adaptation scope.",
    )
    authorized_modifications: list[AuthorizedModification] = Field(
        default_factory=list,
        description="Modification classes permitted downstream.",
    )
    adaptation_constraints: list[str] = Field(
        default_factory=list,
        description="What must not change during adaptation.",
    )
    adaptation_triggers: list[AdaptationTrigger] = Field(
        default_factory=list,
        description="Triggers motivating adaptation.",
    )
    adaptation_deferred: bool = Field(
        default=False,
        description="True when detailed adaptation scope awaits Repository Understanding.",
    )


class GenerationTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysis_module: AnalysisModule = Field(
        description="Analysis module reference — not module content.",
    )
    generation_intent: GenerationIntent = Field(
        description="Intent for generating this analysis module.",
    )
    priority: GenerationPriority = Field(
        default=GenerationPriority.BLOCKING,
        description="Priority of this generation target.",
    )


class GenerationPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    generation_required: bool = Field(
        default=False,
        description="Whether Implementation must generate new artifacts.",
    )
    generation_scope: GenerationScope = Field(
        default=GenerationScope.NONE,
        description="Scope of generation commitment.",
    )
    modules_to_generate: list[GenerationTarget] = Field(
        default_factory=list,
        description="Analysis-aligned generation targets.",
    )
    generation_constraints: list[str] = Field(
        default_factory=list,
        description="Constraints on generated code.",
    )
    generation_rationale: str = Field(
        default="",
        description="Why generation was chosen over reuse.",
    )
    reuse_fallback_after_generation: bool = Field(
        default=False,
        description="Whether discovery resources remain fallbacks after partial generation.",
    )


class RiskRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    risk_id: str = Field(description="Unique risk ID within the artifact.")
    severity: RiskSeverity = Field(description="Risk severity classification.")
    category: RiskCategory = Field(description="Risk category.")
    description: str = Field(default="", description="Human-readable risk statement.")
    mitigation: str = Field(
        default="",
        description="How strategy mitigates or accepts the risk.",
    )
    related_binding_id: str | None = Field(
        default=None,
        description="Optional resource binding reference.",
    )
    related_discovery_gap_id: str | None = Field(
        default=None,
        description="Optional discovery gap reference.",
    )


class FallbackStrategy(BaseModel):
    model_config = ConfigDict(frozen=True)

    fallback_order: int = Field(description="Priority order for this fallback.")
    posture: StrategyPosture = Field(description="Alternative posture to attempt.")
    trigger_condition: str = Field(
        default="",
        description="Condition that activates this fallback.",
    )
    fallback_binding_ids: list[str] = Field(
        default_factory=list,
        description="Optional alternate binding IDs for the fallback.",
    )


class ManualAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    action_id: str = Field(description="Unique manual action ID within the artifact.")
    description: str = Field(default="", description="What the human must do.")
    blocks_planner: bool = Field(
        default=False,
        description="Whether Planner must wait for this action.",
    )


class RiskAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Campaign-level confidence after risk adjustment.",
    )
    blocking_risks: list[RiskRecord] = Field(
        default_factory=list,
        description="Risks that block full reproduction scope.",
    )
    degraded_risks: list[RiskRecord] = Field(
        default_factory=list,
        description="Risks accepted with narrowed or partial scope.",
    )
    informational_risks: list[RiskRecord] = Field(
        default_factory=list,
        description="Risks recorded for audit only.",
    )
    fallback_strategies: list[FallbackStrategy] = Field(
        default_factory=list,
        description="Ordered fallback strategies if primary strategy fails.",
    )
    accepted_discovery_gap_ids: list[str] = Field(
        default_factory=list,
        description="Discovery gap IDs explicitly accepted.",
    )
    manual_actions_required: list[ManualAction] = Field(
        default_factory=list,
        description="Human steps required before Implementation.",
    )
    abort_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions under which the campaign should stop.",
    )


class DecisionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: str = Field(description="Unique decision ID within the trace.")
    decision_category: DecisionCategory = Field(
        description="Category of engineering decision recorded.",
    )
    summary: str = Field(default="", description="What was decided.")
    inputs_consulted: list[str] = Field(
        default_factory=list,
        description="Upstream reference keys consulted — references only.",
    )
    timestamp: datetime | None = Field(
        default=None,
        description="When the decision was recorded.",
    )


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    planning_run_id: str = Field(
        default="",
        description="Correlates with workflow or MLflow nested run.",
    )
    pipeline_version: str = Field(
        default="",
        description="Man1Lab version that produced this artifact.",
    )
    stage_timestamps: dict[str, datetime] = Field(
        default_factory=dict,
        description="Stage name to completion timestamp.",
    )
    degradation_notes: list[str] = Field(
        default_factory=list,
        description="Partial inputs, policy limits, or recovered planning failures.",
    )
    configuration_fingerprint: str = Field(
        default="",
        description="Hash of planning-relevant settings.",
    )
    decision_trace: list[DecisionRecord] = Field(
        default_factory=list,
        description="Structured audit of major decisions.",
    )
    rerun_of: str | None = Field(
        default=None,
        description="Prior strategy_id if this planning run is a replan.",
    )


class ExecutionStrategy(BaseModel):
    model_config = ConfigDict(frozen=True)

    metadata: StrategyMetadata
    input_references: InputReferences
    strategy: Strategy
    resource_bindings: ResourceBindings = Field(default_factory=ResourceBindings)
    reuse_plan: ReusePlan = Field(default_factory=ReusePlan)
    adaptation_plan: AdaptationPlan = Field(default_factory=AdaptationPlan)
    generation_plan: GenerationPlan = Field(default_factory=GenerationPlan)
    risk_assessment: RiskAssessment = Field(default_factory=RiskAssessment)
    provenance: Provenance = Field(default_factory=Provenance)
    schema_version: str = Field(
        default=SCHEMA_VERSION,
        description="ExecutionStrategy schema version.",
    )
