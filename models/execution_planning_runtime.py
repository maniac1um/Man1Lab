"""Runtime stage contracts for Execution Planning workflow.

These models are workflow-internal only. They are not canonical artifacts and
must not leave the Execution Planning capability. Only ExecutionStrategy is
published downstream.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from models.execution_strategy import (
    AdaptationScope,
    AdaptationTrigger,
    AuthorizedModification,
    ExcludedComponent,
    FallbackStrategy,
    GenerationScope,
    GenerationTarget,
    ManualAction,
    PlanningStatus,
    RejectedPosture,
    ResourceBinding,
    ReuseComponent,
    ReuseMode,
    RiskRecord,
    ScopeCommitment,
    StrategyPosture,
)


class StageRuntimeStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    SKIPPED = "skipped"


class PlanningStageRuntimeBase(BaseModel):
    """Common runtime metadata shared by all planning stage results."""

    model_config = ConfigDict(frozen=True)

    stage_name: str = Field(description="Workflow stage identifier for this result.")
    started_at: datetime | None = Field(
        default=None,
        description="When this stage started execution.",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When this stage completed execution.",
    )
    stage_status: StageRuntimeStatus = Field(
        default=StageRuntimeStatus.SUCCESS,
        description="Outcome status for this stage only.",
    )
    decision_notes: str = Field(
        default="",
        description="Human-readable stage summary for provenance.decision_trace.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues observed during the stage.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Recoverable errors recorded without aborting the workflow.",
    )
    diagnostics: dict[str, str] = Field(
        default_factory=dict,
        description="Structured diagnostic key-value pairs for debugging.",
    )


class StrategyDecisionSnapshot(BaseModel):
    """Runtime snapshot of stage 1 outputs; maps to ExecutionStrategy.strategy."""

    model_config = ConfigDict(frozen=True)

    primary_posture: StrategyPosture = Field(description="Committed engineering posture.")
    scope_commitment: ScopeCommitment = Field(
        default=ScopeCommitment.FULL_REPRODUCTION,
        description="Committed reproduction scope.",
    )
    scope_narrowing_rationale: str | None = Field(
        default=None,
        description="Rationale when scope is narrowed.",
    )
    rationale: str = Field(default="", description="Primary strategy explanation.")
    deciding_factors: list[str] = Field(
        default_factory=list,
        description="Named factors informing the strategy decision.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Initial strategy confidence before risk adjustment.",
    )
    alternative_postures_rejected: list[RejectedPosture] = Field(
        default_factory=list,
        description="Rejected alternative postures for audit.",
    )
    artifact_status_hint: PlanningStatus = Field(
        default=PlanningStatus.PARTIAL,
        description="Suggested metadata.status before final risk assessment.",
    )


class ResourceBindingSnapshot(BaseModel):
    """Runtime snapshot of stage 2 outputs; maps to ExecutionStrategy.resource_bindings."""

    model_config = ConfigDict(frozen=True)

    bindings: list[ResourceBinding] = Field(
        default_factory=list,
        description="Resource bindings selected for the campaign.",
    )
    anchor_binding_id: str | None = Field(
        default=None,
        description="Binding ID anchoring the workspace.",
    )
    combination_rationale: str = Field(
        default="",
        description="Why the bound resource set is coherent.",
    )
    selection_alignment_summary: str = Field(
        default="",
        description="How bindings relate to discovery selections.",
    )


class ReusePlanSnapshot(BaseModel):
    """Runtime snapshot of stage 3 outputs; maps to ExecutionStrategy.reuse_plan."""

    model_config = ConfigDict(frozen=True)

    reuse_mode: ReuseMode = Field(
        default=ReuseMode.NOT_APPLICABLE,
        description="Committed reuse mode.",
    )
    primary_reuse_binding_id: str | None = Field(
        default=None,
        description="Primary binding targeted for reuse.",
    )
    components_to_reuse: list[ReuseComponent] = Field(
        default_factory=list,
        description="Components committed to reuse.",
    )
    components_excluded: list[ExcludedComponent] = Field(
        default_factory=list,
        description="Discovered resources explicitly excluded from reuse.",
    )
    reuse_assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions reuse depends on.",
    )
    reuse_limitations: list[str] = Field(
        default_factory=list,
        description="Accepted reuse limitations.",
    )


class AdaptationPlanSnapshot(BaseModel):
    """Runtime snapshot of stage 4 outputs; maps to ExecutionStrategy.adaptation_plan."""

    model_config = ConfigDict(frozen=True)

    adaptation_required: bool = Field(
        default=False,
        description="Whether downstream adaptation is authorized.",
    )
    adaptation_scope: AdaptationScope = Field(
        default=AdaptationScope.NONE,
        description="Authorized adaptation scope.",
    )
    authorized_modifications: list[AuthorizedModification] = Field(
        default_factory=list,
        description="Permitted modification classes.",
    )
    adaptation_constraints: list[str] = Field(
        default_factory=list,
        description="Elements that must not change during adaptation.",
    )
    adaptation_triggers: list[AdaptationTrigger] = Field(
        default_factory=list,
        description="Triggers motivating adaptation.",
    )
    adaptation_deferred: bool = Field(
        default=False,
        description="Whether adaptation scope awaits Repository Understanding.",
    )


class GenerationPlanSnapshot(BaseModel):
    """Runtime snapshot of stage 5 outputs; maps to ExecutionStrategy.generation_plan."""

    model_config = ConfigDict(frozen=True)

    generation_required: bool = Field(
        default=False,
        description="Whether implementation must generate artifacts.",
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
        description="Constraints on generated artifacts.",
    )
    generation_rationale: str = Field(
        default="",
        description="Why generation was chosen over reuse.",
    )
    reuse_fallback_after_generation: bool = Field(
        default=False,
        description="Whether discovery resources remain fallbacks after generation.",
    )


class RiskAssessmentSnapshot(BaseModel):
    """Runtime snapshot of stage 6 outputs; maps to ExecutionStrategy.risk_assessment."""

    model_config = ConfigDict(frozen=True)

    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Campaign confidence after risk recording.",
    )
    blocking_risks: list[RiskRecord] = Field(
        default_factory=list,
        description="Blocking risks recorded by the stage.",
    )
    degraded_risks: list[RiskRecord] = Field(
        default_factory=list,
        description="Degraded risks accepted by the stage.",
    )
    informational_risks: list[RiskRecord] = Field(
        default_factory=list,
        description="Informational risks recorded for audit.",
    )
    fallback_strategies: list[FallbackStrategy] = Field(
        default_factory=list,
        description="Ordered fallback strategies.",
    )
    accepted_discovery_gap_ids: list[str] = Field(
        default_factory=list,
        description="Discovery gap IDs explicitly accepted.",
    )
    manual_actions_required: list[ManualAction] = Field(
        default_factory=list,
        description="Manual actions required before Planner proceeds.",
    )
    abort_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions under which the campaign should stop.",
    )
    artifact_status_hint: PlanningStatus = Field(
        default=PlanningStatus.PARTIAL,
        description="Final suggested metadata.status for assembly.",
    )


class StrategyDecisionResult(PlanningStageRuntimeBase):
    """Runtime result for stage 1 — Strategy Decision."""

    stage_name: str = Field(default="strategy_decision")
    strategy: StrategyDecisionSnapshot = Field(
        description="Stage 1 engineering posture decision.",
    )


class ResourceBindingResult(PlanningStageRuntimeBase):
    """Runtime result for stage 2 — Resource Binding."""

    stage_name: str = Field(default="resource_binding")
    strategy: StrategyDecisionSnapshot = Field(
        description="Pass-through strategy decision from stage 1.",
    )
    resource_bindings: ResourceBindingSnapshot = Field(
        default_factory=ResourceBindingSnapshot,
        description="Stage 2 resource binding outputs.",
    )


class ReusePlanResult(PlanningStageRuntimeBase):
    """Runtime result for stage 3 — Reuse Planning."""

    stage_name: str = Field(default="reuse_planning")
    strategy: StrategyDecisionSnapshot = Field(
        description="Pass-through strategy decision from stage 1.",
    )
    resource_bindings: ResourceBindingSnapshot = Field(
        default_factory=ResourceBindingSnapshot,
        description="Pass-through resource bindings from stage 2.",
    )
    reuse_plan: ReusePlanSnapshot = Field(
        default_factory=ReusePlanSnapshot,
        description="Stage 3 reuse planning outputs.",
    )


class AdaptationPlanResult(PlanningStageRuntimeBase):
    """Runtime result for stage 4 — Adaptation Planning."""

    stage_name: str = Field(default="adaptation_planning")
    strategy: StrategyDecisionSnapshot = Field(
        description="Pass-through strategy decision from stage 1.",
    )
    resource_bindings: ResourceBindingSnapshot = Field(
        default_factory=ResourceBindingSnapshot,
        description="Pass-through resource bindings from stage 2.",
    )
    reuse_plan: ReusePlanSnapshot = Field(
        default_factory=ReusePlanSnapshot,
        description="Pass-through reuse plan from stage 3.",
    )
    adaptation_plan: AdaptationPlanSnapshot = Field(
        default_factory=AdaptationPlanSnapshot,
        description="Stage 4 adaptation planning outputs.",
    )


class GenerationPlanResult(PlanningStageRuntimeBase):
    """Runtime result for stage 5 — Generation Planning."""

    stage_name: str = Field(default="generation_planning")
    strategy: StrategyDecisionSnapshot = Field(
        description="Pass-through strategy decision from stage 1.",
    )
    resource_bindings: ResourceBindingSnapshot = Field(
        default_factory=ResourceBindingSnapshot,
        description="Pass-through resource bindings from stage 2.",
    )
    reuse_plan: ReusePlanSnapshot = Field(
        default_factory=ReusePlanSnapshot,
        description="Pass-through reuse plan from stage 3.",
    )
    adaptation_plan: AdaptationPlanSnapshot = Field(
        default_factory=AdaptationPlanSnapshot,
        description="Pass-through adaptation plan from stage 4.",
    )
    generation_plan: GenerationPlanSnapshot = Field(
        default_factory=GenerationPlanSnapshot,
        description="Stage 5 generation planning outputs.",
    )


class RiskAssessmentResult(PlanningStageRuntimeBase):
    """Runtime result for stage 6 — Risk Assessment."""

    stage_name: str = Field(default="risk_assessment")
    strategy: StrategyDecisionSnapshot = Field(
        description="Pass-through strategy decision; unchanged by this stage.",
    )
    resource_bindings: ResourceBindingSnapshot = Field(
        default_factory=ResourceBindingSnapshot,
        description="Pass-through resource bindings; unchanged by this stage.",
    )
    reuse_plan: ReusePlanSnapshot = Field(
        default_factory=ReusePlanSnapshot,
        description="Pass-through reuse plan; unchanged by this stage.",
    )
    adaptation_plan: AdaptationPlanSnapshot = Field(
        default_factory=AdaptationPlanSnapshot,
        description="Pass-through adaptation plan; unchanged by this stage.",
    )
    generation_plan: GenerationPlanSnapshot = Field(
        default_factory=GenerationPlanSnapshot,
        description="Pass-through generation plan; unchanged by this stage.",
    )
    risk_assessment: RiskAssessmentSnapshot = Field(
        default_factory=RiskAssessmentSnapshot,
        description="Stage 6 risk assessment outputs.",
    )
