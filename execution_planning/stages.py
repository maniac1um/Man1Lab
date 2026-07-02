"""Deterministic Execution Planning stage logic — consumes canonical artifacts only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from models.execution_planning_runtime import (
    AdaptationPlanResult,
    AdaptationPlanSnapshot,
    GenerationPlanResult,
    GenerationPlanSnapshot,
    ResourceBindingResult,
    ResourceBindingSnapshot,
    ReusePlanResult,
    ReusePlanSnapshot,
    RiskAssessmentResult,
    RiskAssessmentSnapshot,
    StageRuntimeStatus,
    StrategyDecisionResult,
    StrategyDecisionSnapshot,
)
from models.execution_strategy import (
    AdaptationScope,
    AdaptationTrigger,
    AdaptationTriggerType,
    AnalysisModule,
    BindingRole,
    GenerationIntent,
    GenerationPriority,
    GenerationScope,
    GenerationTarget,
    PlanningStatus,
    RejectedPosture,
    ResourceBinding,
    ReuseMode,
    RiskCategory,
    RiskRecord,
    RiskSeverity,
    ScopeCommitment,
    StrategyPosture,
    UsageIntent,
)
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    DiscoveryStatus,
    NeedCategory,
    Officiality,
    RankList,
    RepositoryCandidate,
    ResearchResourceDiscovery,
    ResourceType,
    VerificationRecord,
    VerificationStatus,
)


def run_strategy_decision(
    analysis: PaperReproductionAnalysis,
    discovery: ResearchResourceDiscovery,
    *,
    started_at: datetime,
) -> StrategyDecisionResult:
    primary = _select_primary_candidate(discovery)
    posture, rationale, factors, rejected, confidence, status_hint = _decide_posture(
        analysis,
        discovery,
        primary,
    )
    scope = _scope_commitment(analysis)
    return StrategyDecisionResult(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        stage_status=StageRuntimeStatus.PARTIAL if not primary else StageRuntimeStatus.SUCCESS,
        decision_notes=rationale,
        strategy=StrategyDecisionSnapshot(
            primary_posture=posture,
            scope_commitment=scope,
            rationale=rationale,
            deciding_factors=factors,
            confidence=confidence,
            alternative_postures_rejected=rejected,
            artifact_status_hint=status_hint,
        ),
    )


def run_resource_binding(
    analysis: PaperReproductionAnalysis,
    discovery: ResearchResourceDiscovery,
    strategy_result: StrategyDecisionResult,
    *,
    started_at: datetime,
) -> ResourceBindingResult:
    del analysis
    bindings: list[ResourceBinding] = []
    selection_ids: list[str] = []
    primary = _select_primary_candidate(discovery)
    if primary is not None and strategy_result.strategy.primary_posture != StrategyPosture.GREENFIELD:
        need_id = primary.addresses_needs[0] if primary.addresses_needs else None
        selection_id = f"selection-{need_id}" if need_id else None
        if selection_id:
            selection_ids.append(selection_id)
        binding_id = f"binding-{primary.candidate_id}"
        bindings.append(
            ResourceBinding(
                binding_id=binding_id,
                candidate_id=primary.candidate_id,
                selection_id=selection_id,
                resource_need_id=need_id,
                role=BindingRole.PRIMARY_REPOSITORY,
                usage_intent=UsageIntent.EXECUTE_DIRECTLY,
                binding_rationale="Top-ranked eligible discovery candidate.",
            )
        )
        fallbacks = _fallback_candidates(discovery, exclude_id=primary.candidate_id)
        for index, candidate in enumerate(fallbacks, start=1):
            bindings.append(
                ResourceBinding(
                    binding_id=f"binding-fallback-{index}-{candidate.candidate_id}",
                    candidate_id=candidate.candidate_id,
                    selection_id=selection_id,
                    resource_need_id=need_id,
                    role=BindingRole.FALLBACK_REPOSITORY,
                    usage_intent=UsageIntent.FALLBACK_IF_PRIMARY_FAILS,
                    binding_rationale="Ranked fallback repository candidate.",
                )
            )
    anchor = bindings[0].binding_id if bindings else None
    return ResourceBindingResult(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        stage_status=StageRuntimeStatus.PARTIAL if not bindings and strategy_result.strategy.primary_posture != StrategyPosture.GREENFIELD else StageRuntimeStatus.SUCCESS,
        decision_notes="Bound discovery candidates to execution roles.",
        strategy=strategy_result.strategy,
        resource_bindings=ResourceBindingSnapshot(
            bindings=bindings,
            anchor_binding_id=anchor,
            combination_rationale="Bindings derived from discovery ranking and verification.",
            selection_alignment_summary=(
                f"Aligned with discovery selections: {', '.join(selection_ids)}"
                if selection_ids
                else "No discovery selection alignment — greenfield or empty discovery."
            ),
        ),
    )


def run_reuse_planning(
    binding_result: ResourceBindingResult,
    *,
    started_at: datetime,
) -> ReusePlanResult:
    posture = binding_result.strategy.primary_posture
    if posture in {StrategyPosture.OFFICIAL_REPOSITORY, StrategyPosture.COMMUNITY_FORK, StrategyPosture.HYBRID}:
        reuse_mode = ReuseMode.AS_IS
        primary_binding = binding_result.resource_bindings.anchor_binding_id
        assumptions = ["Repository executes with paper-aligned entrypoints."]
    else:
        reuse_mode = ReuseMode.NOT_APPLICABLE
        primary_binding = None
        assumptions = []
    return ReusePlanResult(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        stage_status=StageRuntimeStatus.SUCCESS,
        decision_notes=f"Reuse mode committed: {reuse_mode.value}.",
        strategy=binding_result.strategy,
        resource_bindings=binding_result.resource_bindings,
        reuse_plan=ReusePlanSnapshot(
            reuse_mode=reuse_mode,
            primary_reuse_binding_id=primary_binding,
            reuse_assumptions=assumptions,
        ),
    )


def run_adaptation_planning(
    discovery: ResearchResourceDiscovery,
    reuse_result: ReusePlanResult,
    *,
    started_at: datetime,
) -> AdaptationPlanResult:
    partial = _has_partial_verification(discovery)
    required = partial and reuse_result.reuse_plan.reuse_mode != ReuseMode.NOT_APPLICABLE
    scope = AdaptationScope.MINIMAL if required else AdaptationScope.NONE
    triggers = []
    if required:
        triggers.append(
            AdaptationTrigger(
                trigger_type=AdaptationTriggerType.VERIFICATION_PARTIAL,
                description="Discovery verification returned partial status.",
            )
        )
    return AdaptationPlanResult(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        stage_status=StageRuntimeStatus.PARTIAL if required else StageRuntimeStatus.SUCCESS,
        decision_notes="Adaptation scope derived from verification outcomes.",
        strategy=reuse_result.strategy,
        resource_bindings=reuse_result.resource_bindings,
        reuse_plan=reuse_result.reuse_plan,
        adaptation_plan=AdaptationPlanSnapshot(
            adaptation_required=required,
            adaptation_scope=scope,
            adaptation_constraints=["Do not change committed model architecture."],
            adaptation_triggers=triggers,
        ),
    )


def run_generation_planning(
    analysis: PaperReproductionAnalysis,
    adaptation_result: AdaptationPlanResult,
    *,
    started_at: datetime,
) -> GenerationPlanResult:
    posture = adaptation_result.strategy.primary_posture
    framework = analysis.method.framework or "unspecified"
    if posture == StrategyPosture.GREENFIELD:
        generation_required = True
        generation_scope = GenerationScope.FULL_CODEBASE
        rationale = "No reusable repository — generate implementation from analysis."
        modules = [
            GenerationTarget(
                analysis_module=AnalysisModule.METHOD,
                generation_intent=GenerationIntent.IMPLEMENT_FROM_PAPER,
                priority=GenerationPriority.BLOCKING,
            ),
            GenerationTarget(
                analysis_module=AnalysisModule.EVALUATION,
                generation_intent=GenerationIntent.IMPLEMENT_FROM_PAPER,
                priority=GenerationPriority.BLOCKING,
            ),
        ]
    elif adaptation_result.adaptation_plan.adaptation_required:
        generation_required = True
        generation_scope = GenerationScope.MISSING_MODULES
        rationale = "Generate missing modules to complete partial repository."
        modules = [
            GenerationTarget(
                analysis_module=AnalysisModule.EVALUATION,
                generation_intent=GenerationIntent.STUB_FOR_INTEGRATION,
                priority=GenerationPriority.DEGRADED,
            )
        ]
    else:
        generation_required = False
        generation_scope = GenerationScope.NONE
        rationale = "Repository reuse covers implementation scope."
        modules = []
    return GenerationPlanResult(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        stage_status=StageRuntimeStatus.SUCCESS,
        decision_notes=rationale,
        strategy=adaptation_result.strategy,
        resource_bindings=adaptation_result.resource_bindings,
        reuse_plan=adaptation_result.reuse_plan,
        adaptation_plan=adaptation_result.adaptation_plan,
        generation_plan=GenerationPlanSnapshot(
            generation_required=generation_required,
            generation_scope=generation_scope,
            modules_to_generate=modules,
            generation_rationale=rationale,
            generation_constraints=[f"Framework: {framework}"],
        ),
    )


def run_risk_assessment(
    discovery: ResearchResourceDiscovery,
    generation_result: GenerationPlanResult,
    *,
    started_at: datetime,
) -> RiskAssessmentResult:
    blocking: list[RiskRecord] = []
    degraded: list[RiskRecord] = []
    informational: list[RiskRecord] = []
    accepted_gap_ids: list[str] = []

    for gap in discovery.discovery_gaps.gaps:
        if gap.severity.value == "blocking":
            blocking.append(
                RiskRecord(
                    risk_id=f"risk-{gap.gap_id}",
                    severity=RiskSeverity.BLOCKING,
                    category=RiskCategory.UNRESOLVED_RESOURCE,
                    description=gap.description,
                    related_discovery_gap_id=gap.gap_id,
                )
            )
        elif gap.severity.value == "degraded":
            degraded.append(
                RiskRecord(
                    risk_id=f"risk-{gap.gap_id}",
                    severity=RiskSeverity.DEGRADED,
                    category=RiskCategory.UNRESOLVED_RESOURCE,
                    description=gap.description,
                    related_discovery_gap_id=gap.gap_id,
                )
            )
        else:
            informational.append(
                RiskRecord(
                    risk_id=f"risk-{gap.gap_id}",
                    severity=RiskSeverity.INFORMATIONAL,
                    category=RiskCategory.OTHER,
                    description=gap.description,
                    related_discovery_gap_id=gap.gap_id,
                )
            )
            accepted_gap_ids.append(gap.gap_id)

    confidence = generation_result.strategy.confidence
    if blocking:
        confidence = min(confidence, 0.4)
    elif degraded:
        confidence = min(confidence, 0.7)

    if blocking:
        status_hint = PlanningStatus.PARTIAL
    elif discovery.metadata.status == DiscoveryStatus.PARTIAL:
        status_hint = PlanningStatus.PARTIAL
    elif generation_result.generation_plan.generation_required:
        status_hint = PlanningStatus.DEGRADED
    else:
        status_hint = PlanningStatus.COMPLETE

    return RiskAssessmentResult(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        stage_status=StageRuntimeStatus.DEGRADED if degraded else StageRuntimeStatus.SUCCESS,
        decision_notes="Recorded discovery and strategy risks.",
        strategy=generation_result.strategy,
        resource_bindings=generation_result.resource_bindings,
        reuse_plan=generation_result.reuse_plan,
        adaptation_plan=generation_result.adaptation_plan,
        generation_plan=generation_result.generation_plan,
        risk_assessment=RiskAssessmentSnapshot(
            overall_confidence=confidence,
            blocking_risks=blocking,
            degraded_risks=degraded,
            informational_risks=informational,
            accepted_discovery_gap_ids=accepted_gap_ids,
            artifact_status_hint=status_hint,
        ),
    )


def _decide_posture(
    analysis: PaperReproductionAnalysis,
    discovery: ResearchResourceDiscovery,
    primary: RepositoryCandidate | None,
) -> tuple[StrategyPosture, str, list[str], list[RejectedPosture], float, PlanningStatus]:
    del analysis
    if primary is None:
        return (
            StrategyPosture.GREENFIELD,
            "No eligible discovery candidate — commit to greenfield implementation.",
            ["discovery_empty", "no_verified_repository"],
            [
                RejectedPosture(
                    posture=StrategyPosture.OFFICIAL_REPOSITORY,
                    rejection_reason="No verified official repository candidate.",
                )
            ],
            0.5,
            PlanningStatus.PARTIAL,
        )

    verification = _verification_for(discovery, primary.candidate_id)
    status = verification.status if verification else VerificationStatus.SKIPPED
    factors = [f"candidate:{primary.candidate_id}", f"verification:{status.value}"]

    if primary.resource_type == ResourceType.OFFICIAL_REPOSITORY and status == VerificationStatus.PASS:
        return (
            StrategyPosture.OFFICIAL_REPOSITORY,
            f"Verified official repository selected: {primary.url or primary.candidate_id}.",
            factors + ["official_repository", "verification_pass"],
            [
                RejectedPosture(
                    posture=StrategyPosture.GREENFIELD,
                    rejection_reason="Verified official repository available.",
                )
            ],
            0.9,
            PlanningStatus.COMPLETE,
        )

    if status in {VerificationStatus.PASS, VerificationStatus.PARTIAL}:
        posture = (
            StrategyPosture.COMMUNITY_FORK
            if primary.officiality.value == "community"
            else StrategyPosture.HYBRID
        )
        return (
            posture,
            f"Reuse discovered repository with {status.value} verification: {primary.candidate_id}.",
            factors + [posture.value],
            [
                RejectedPosture(
                    posture=StrategyPosture.GREENFIELD,
                    rejection_reason="Reusable repository candidate available.",
                )
            ],
            0.75 if status == VerificationStatus.PARTIAL else 0.85,
            PlanningStatus.PARTIAL if status == VerificationStatus.PARTIAL else PlanningStatus.COMPLETE,
        )

    return (
        StrategyPosture.GREENFIELD,
        "Discovery candidates failed verification — greenfield implementation required.",
        factors + ["verification_fail"],
        [
            RejectedPosture(
                posture=StrategyPosture.OFFICIAL_REPOSITORY,
                rejection_reason="Candidates did not pass verification.",
            )
        ],
        0.55,
        PlanningStatus.PARTIAL,
    )


def _scope_commitment(analysis: PaperReproductionAnalysis) -> ScopeCommitment:
    scope = analysis.goal.scope.value if analysis.goal.scope else ""
    if scope == "eval_only":
        return ScopeCommitment.EVAL_ONLY
    if scope == "inference_only":
        return ScopeCommitment.INFERENCE_ONLY
    return ScopeCommitment.FULL_REPRODUCTION


def _select_primary_candidate(
    discovery: ResearchResourceDiscovery,
) -> RepositoryCandidate | None:
    candidate_map = {
        candidate.candidate_id: candidate
        for candidate in discovery.candidate_resources.candidates
    }
    for rank_list in _repository_rank_lists(discovery):
        for candidate_id in rank_list.eligible_candidate_ids or rank_list.ordered_candidate_ids:
            candidate = candidate_map.get(candidate_id)
            if candidate is not None:
                return candidate
    return None


def _fallback_candidates(
    discovery: ResearchResourceDiscovery,
    *,
    exclude_id: str,
) -> list[RepositoryCandidate]:
    candidate_map = {
        candidate.candidate_id: candidate
        for candidate in discovery.candidate_resources.candidates
    }
    fallbacks: list[RepositoryCandidate] = []
    for rank_list in _repository_rank_lists(discovery):
        ordered = rank_list.ordered_candidate_ids
        for candidate_id in ordered:
            if candidate_id == exclude_id:
                continue
            candidate = candidate_map.get(candidate_id)
            if candidate is not None:
                fallbacks.append(candidate)
    return fallbacks[:3]


def _repository_rank_lists(discovery: ResearchResourceDiscovery) -> list[RankList]:
    return [
        rank_list
        for rank_list in discovery.ranking.rank_lists
        if rank_list.resource_need.need_category == NeedCategory.CODE_REPOSITORY
    ]


def _verification_for(
    discovery: ResearchResourceDiscovery,
    candidate_id: str,
) -> VerificationRecord | None:
    for record in discovery.verification.records:
        if record.candidate_id == candidate_id:
            return record
    return None


def _has_partial_verification(discovery: ResearchResourceDiscovery) -> bool:
    return any(
        record.status == VerificationStatus.PARTIAL
        for record in discovery.verification.records
    )


def new_strategy_id() -> str:
    return f"strategy-{uuid.uuid4()}"
