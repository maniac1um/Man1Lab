"""Execution readiness assessment and risk decision from completed planning outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from models.execution_planning_runtime import (
    AdaptationPlanSnapshot,
    GenerationPlanSnapshot,
    ResourceBindingSnapshot,
    ReusePlanSnapshot,
    StrategyDecisionSnapshot,
)
from models.execution_strategy import (
    FallbackStrategy,
    ManualAction,
    PlanningStatus,
    RiskCategory,
    RiskRecord,
    RiskSeverity,
    ReuseMode,
    StrategyPosture,
)
from models.research_resource_discovery import GapSeverity
from providers.embedded.decision_foundation.common import (
    confidence_string,
    dimension_factor,
    provider_name_factor,
)
from providers.embedded.decision_foundation.dimensions import DecisionDimensions, DimensionLevel
from providers.embedded.decision_foundation.facts import ObservedFacts

_PROVIDER_NAME = "embedded_risk"

_SUPPORTING_LABELS = frozenset({"fallback_repository", "supporting_asset"})


class ReadinessLevel(str, Enum):
    READY = "ready"
    PARTIAL = "partial"
    NOT_READY = "not_ready"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExecutionReadiness:
    resource_ready: ReadinessLevel
    engineering_ready: ReadinessLevel
    dependency_ready: ReadinessLevel
    execution_ready: ReadinessLevel


@dataclass(frozen=True)
class RiskDecision:
    blocking_risks: tuple[RiskRecord, ...]
    degraded_risks: tuple[RiskRecord, ...]
    informational_risks: tuple[RiskRecord, ...]
    fallback_strategies: tuple[FallbackStrategy, ...]
    manual_actions_required: tuple[ManualAction, ...]
    accepted_discovery_gap_ids: tuple[str, ...]
    abort_conditions: tuple[str, ...]
    overall_confidence: float
    artifact_status_hint: PlanningStatus
    assessment_rationale: str
    decision_notes: tuple[str, ...]
    provider_factors: tuple[str, ...]
    diagnostics: dict[str, str]
    warnings: tuple[str, ...]


def evaluate_execution_readiness(
    facts: ObservedFacts,
    dimensions: DecisionDimensions,
    strategy: StrategyDecisionSnapshot,
    bindings: ResourceBindingSnapshot,
    reuse_plan: ReusePlanSnapshot,
    adaptation_plan: AdaptationPlanSnapshot,
    generation_plan: GenerationPlanSnapshot,
) -> ExecutionReadiness:
    return ExecutionReadiness(
        resource_ready=_resource_ready(facts, bindings, strategy),
        engineering_ready=_engineering_ready(strategy, reuse_plan, adaptation_plan, generation_plan, dimensions),
        dependency_ready=_dependency_ready(facts, dimensions),
        execution_ready=_execution_ready(
            facts,
            dimensions,
            strategy,
            bindings,
            reuse_plan,
            adaptation_plan,
            generation_plan,
        ),
    )


def decide_risk(
    facts: ObservedFacts,
    dimensions: DecisionDimensions,
    readiness: ExecutionReadiness,
    strategy: StrategyDecisionSnapshot,
    bindings: ResourceBindingSnapshot,
    reuse_plan: ReusePlanSnapshot,
    adaptation_plan: AdaptationPlanSnapshot,
    generation_plan: GenerationPlanSnapshot,
) -> RiskDecision:
    blocking: list[RiskRecord] = []
    degraded: list[RiskRecord] = []
    informational: list[RiskRecord] = []
    notes = ["Evaluating completed execution plan for residual risks."]

    anchor_binding_id = bindings.anchor_binding_id

    if strategy.primary_posture == StrategyPosture.GREENFIELD:
        degraded.append(
            RiskRecord(
                risk_id="risk-engineering-greenfield",
                severity=RiskSeverity.DEGRADED,
                category=RiskCategory.SCOPE_MISMATCH,
                description="Greenfield posture carries higher engineering implementation risk.",
                mitigation="Generation plan commits scaffolding artifacts before execution.",
            )
        )
        notes.append("Greenfield implementation risk recorded.")

    if strategy.primary_posture == StrategyPosture.HYBRID or reuse_plan.reuse_mode == ReuseMode.HYBRID_COMPONENTS:
        degraded.append(
            RiskRecord(
                risk_id="risk-integration-hybrid",
                severity=RiskSeverity.DEGRADED,
                category=RiskCategory.SCOPE_MISMATCH,
                description="Hybrid reuse introduces integration risk across partial resources.",
                mitigation="Adaptation and generation plans authorize targeted engineering work.",
                related_binding_id=anchor_binding_id,
            )
        )
        notes.append("Hybrid integration risk recorded.")

    if (
        strategy.primary_posture == StrategyPosture.OFFICIAL_REPOSITORY
        and reuse_plan.reuse_mode == ReuseMode.AS_IS
        and not adaptation_plan.adaptation_required
    ):
        informational.append(
            RiskRecord(
                risk_id="risk-info-official-repository",
                severity=RiskSeverity.INFORMATIONAL,
                category=RiskCategory.OTHER,
                description="Verified official repository reuse lowers implementation risk.",
                mitigation="Proceed with reuse plan without additional generation.",
                related_binding_id=reuse_plan.primary_reuse_binding_id,
            )
        )
        notes.append("Official repository reuse reduces residual implementation risk.")

    if facts.repository_archived:
        degraded.append(
            RiskRecord(
                risk_id="risk-repository-archived",
                severity=RiskSeverity.DEGRADED,
                category=RiskCategory.UNRESOLVED_RESOURCE,
                description="Repository sustainability risk — selected repository is archived.",
                mitigation="Use supporting repository fallback if primary execution fails.",
                related_binding_id=anchor_binding_id,
            )
        )
        notes.append("Archived repository sustainability risk recorded.")

    if generation_plan.generation_required and not generation_plan.modules_to_generate:
        degraded.append(
            RiskRecord(
                risk_id="risk-execution-generation-gap",
                severity=RiskSeverity.DEGRADED,
                category=RiskCategory.OTHER,
                description="Generation required but no generation targets were committed.",
                mitigation="Re-run generation planning or authorize manual artifact creation.",
            )
        )
        notes.append("Missing generation targets create execution preparation risk.")

    if reuse_plan.reuse_mode == ReuseMode.NOT_APPLICABLE and strategy.primary_posture != StrategyPosture.GREENFIELD:
        degraded.append(
            RiskRecord(
                risk_id="risk-dependency-missing-reuse",
                severity=RiskSeverity.DEGRADED,
                category=RiskCategory.UNRESOLVED_RESOURCE,
                description="No reusable resources committed; dependency risk remains elevated.",
                mitigation="Resource binding and generation plans must satisfy missing dependencies.",
            )
        )

    if _supporting_only_reuse(reuse_plan):
        degraded.append(
            RiskRecord(
                risk_id="risk-maintenance-supporting-only",
                severity=RiskSeverity.DEGRADED,
                category=RiskCategory.VERIFICATION_LOW_CONFIDENCE,
                description="Supporting-only resources increase maintenance and verification risk.",
                mitigation="Prefer primary repository binding when verification succeeds.",
                related_binding_id=_supporting_binding_id(bindings),
            )
        )
        notes.append("Supporting-only reuse maintenance risk recorded.")

    for gap in facts.blocking_discovery_gaps:
        blocking.append(
            RiskRecord(
                risk_id=f"risk-blocking-{gap.gap_id}",
                severity=RiskSeverity.BLOCKING,
                category=RiskCategory.UNRESOLVED_RESOURCE,
                description=f"Blocking discovery gap remains: {gap.gap_type.value}.",
                mitigation="Apply fallback strategy or reduce reproduction scope.",
                related_discovery_gap_id=gap.gap_id,
                related_binding_id=anchor_binding_id,
            )
        )

    for gap in facts.required_resource_gaps:
        if gap.severity == GapSeverity.DEGRADED:
            degraded.append(
                RiskRecord(
                    risk_id=f"risk-degraded-{gap.gap_id}",
                    severity=RiskSeverity.DEGRADED,
                    category=RiskCategory.UNRESOLVED_RESOURCE,
                    description=f"Degraded resource gap accepted: {gap.gap_type.value}.",
                    mitigation="Generation or adaptation plans may partially mitigate this gap.",
                    related_discovery_gap_id=gap.gap_id,
                )
            )

    if readiness.execution_ready == ReadinessLevel.NOT_READY:
        blocking.append(
            RiskRecord(
                risk_id="risk-execution-not-ready",
                severity=RiskSeverity.BLOCKING,
                category=RiskCategory.OTHER,
                description="Execution readiness is not_ready after planning completed.",
                mitigation="Resolve blocking gaps or reduce scope before execution.",
            )
        )

    fallbacks = _fallback_strategies(bindings, reuse_plan, generation_plan, strategy, facts)
    manual_actions = _manual_actions(strategy, generation_plan)
    accepted_gaps = tuple(
        gap.gap_id
        for gap in facts.required_resource_gaps
        if gap.severity == GapSeverity.DEGRADED and gap.gap_id not in {risk.related_discovery_gap_id for risk in blocking}
    )
    abort_conditions = _abort_conditions(blocking, readiness)
    confidence = _overall_confidence(strategy, readiness, blocking, degraded, dimensions)
    status_hint = _artifact_status_hint(blocking, degraded, confidence)

    notes.append(f"Execution readiness: {readiness.execution_ready.value}.")
    notes.append(f"Overall confidence: {confidence:.2f}.")

    return RiskDecision(
        blocking_risks=tuple(blocking),
        degraded_risks=tuple(degraded),
        informational_risks=tuple(informational),
        fallback_strategies=fallbacks,
        manual_actions_required=manual_actions,
        accepted_discovery_gap_ids=accepted_gaps,
        abort_conditions=abort_conditions,
        overall_confidence=confidence,
        artifact_status_hint=status_hint,
        assessment_rationale=_assessment_rationale(strategy, readiness, blocking, degraded),
        decision_notes=tuple(notes),
        provider_factors=_provider_factors(dimensions, readiness, len(blocking), len(degraded)),
        diagnostics=_diagnostics(strategy, reuse_plan, readiness, confidence, blocking, degraded, informational),
        warnings=(),
    )


def _resource_ready(
    facts: ObservedFacts,
    bindings: ResourceBindingSnapshot,
    strategy: StrategyDecisionSnapshot,
) -> ReadinessLevel:
    if strategy.primary_posture == StrategyPosture.GREENFIELD:
        return ReadinessLevel.NOT_READY
    if bindings.bindings and not facts.blocking_discovery_gaps:
        return ReadinessLevel.READY
    if bindings.bindings:
        return ReadinessLevel.PARTIAL
    if facts.repository_usable:
        return ReadinessLevel.PARTIAL
    return ReadinessLevel.NOT_READY


def _engineering_ready(
    strategy: StrategyDecisionSnapshot,
    reuse_plan: ReusePlanSnapshot,
    adaptation_plan: AdaptationPlanSnapshot,
    generation_plan: GenerationPlanSnapshot,
    dimensions: DecisionDimensions,
) -> ReadinessLevel:
    if strategy.primary_posture == StrategyPosture.GREENFIELD:
        return ReadinessLevel.PARTIAL if generation_plan.generation_required else ReadinessLevel.NOT_READY
    if reuse_plan.reuse_mode == ReuseMode.AS_IS and not adaptation_plan.adaptation_required:
        return ReadinessLevel.READY
    if reuse_plan.reuse_mode == ReuseMode.HYBRID_COMPONENTS or adaptation_plan.adaptation_required:
        return ReadinessLevel.PARTIAL
    if dimensions.engineering_commitment == DimensionLevel.HIGH:
        return ReadinessLevel.PARTIAL
    return ReadinessLevel.READY


def _dependency_ready(facts: ObservedFacts, dimensions: DecisionDimensions) -> ReadinessLevel:
    if facts.blocking_discovery_gaps:
        return ReadinessLevel.NOT_READY
    if facts.required_resource_gaps:
        return ReadinessLevel.PARTIAL
    if dimensions.resource_sufficiency == DimensionLevel.HIGH:
        return ReadinessLevel.READY
    if dimensions.resource_sufficiency == DimensionLevel.UNKNOWN:
        return ReadinessLevel.UNKNOWN
    return ReadinessLevel.PARTIAL


def _execution_ready(
    facts: ObservedFacts,
    dimensions: DecisionDimensions,
    strategy: StrategyDecisionSnapshot,
    bindings: ResourceBindingSnapshot,
    reuse_plan: ReusePlanSnapshot,
    adaptation_plan: AdaptationPlanSnapshot,
    generation_plan: GenerationPlanSnapshot,
) -> ReadinessLevel:
    levels = {
        _resource_ready(facts, bindings, strategy),
        _engineering_ready(strategy, reuse_plan, adaptation_plan, generation_plan, dimensions),
        _dependency_ready(facts, dimensions),
    }
    if ReadinessLevel.NOT_READY in levels:
        return ReadinessLevel.NOT_READY
    if ReadinessLevel.UNKNOWN in levels:
        return ReadinessLevel.UNKNOWN
    if ReadinessLevel.PARTIAL in levels:
        return ReadinessLevel.PARTIAL
    return ReadinessLevel.READY


def _supporting_only_reuse(reuse_plan: ReusePlanSnapshot) -> bool:
    if not reuse_plan.components_to_reuse:
        return False
    labels = {component.component_label for component in reuse_plan.components_to_reuse}
    return bool(labels & _SUPPORTING_LABELS) and "repository" not in labels


def _supporting_binding_id(bindings: ResourceBindingSnapshot) -> str | None:
    for binding in bindings.bindings:
        if binding.role.value in {"fallback_repository", "supporting_asset"}:
            return binding.binding_id
    return None


def _fallback_strategies(
    bindings: ResourceBindingSnapshot,
    reuse_plan: ReusePlanSnapshot,
    generation_plan: GenerationPlanSnapshot,
    strategy: StrategyDecisionSnapshot,
    facts: ObservedFacts,
) -> tuple[FallbackStrategy, ...]:
    fallbacks: list[FallbackStrategy] = []
    order = 1
    fallback_ids = [
        binding.binding_id
        for binding in bindings.bindings
        if binding.role.value in {"fallback_repository", "supporting_asset"}
    ]
    if fallback_ids:
        fallbacks.append(
            FallbackStrategy(
                fallback_order=order,
                posture=StrategyPosture.HYBRID,
                trigger_condition="Primary repository execution fails.",
                fallback_binding_ids=fallback_ids,
            )
        )
        order += 1
    if generation_plan.generation_required:
        fallbacks.append(
            FallbackStrategy(
                fallback_order=order,
                posture=strategy.primary_posture,
                trigger_condition="Generate missing configuration before execution retry.",
                fallback_binding_ids=[],
            )
        )
        order += 1
    if facts.required_resource_gaps:
        fallbacks.append(
            FallbackStrategy(
                fallback_order=order,
                posture=StrategyPosture.HYBRID,
                trigger_condition="Required resources remain unavailable.",
                fallback_binding_ids=fallback_ids or [],
            )
        )
        order += 1
    if strategy.primary_posture == StrategyPosture.GREENFIELD:
        fallbacks.append(
            FallbackStrategy(
                fallback_order=order,
                posture=StrategyPosture.MANUAL,
                trigger_condition="Manual engineering required before execution.",
                fallback_binding_ids=[],
            )
        )
    elif strategy.primary_posture == StrategyPosture.HYBRID:
        fallbacks.append(
            FallbackStrategy(
                fallback_order=order,
                posture=StrategyPosture.HYBRID,
                trigger_condition="Reduce reproduction scope when integration fails.",
                fallback_binding_ids=fallback_ids,
            )
        )
    return tuple(fallbacks)


def _manual_actions(
    strategy: StrategyDecisionSnapshot,
    generation_plan: GenerationPlanSnapshot,
) -> tuple[ManualAction, ...]:
    actions: list[ManualAction] = []
    if strategy.primary_posture == StrategyPosture.GREENFIELD:
        actions.append(
            ManualAction(
                action_id="manual-engineering-review",
                description="Review generated scaffolding before execution.",
                blocks_planner=False,
            )
        )
    if generation_plan.generation_required:
        actions.append(
            ManualAction(
                action_id="manual-generation-validation",
                description="Validate committed generation targets before implementation.",
                blocks_planner=False,
            )
        )
    return tuple(actions)


def _abort_conditions(
    blocking: list[RiskRecord],
    readiness: ExecutionReadiness,
) -> tuple[str, ...]:
    conditions: list[str] = []
    if blocking:
        conditions.append("Abort if blocking risks remain unresolved before execution.")
    if readiness.dependency_ready == ReadinessLevel.NOT_READY:
        conditions.append("Abort when required dependencies cannot be satisfied.")
    return tuple(conditions)


def _overall_confidence(
    strategy: StrategyDecisionSnapshot,
    readiness: ExecutionReadiness,
    blocking: list[RiskRecord],
    degraded: list[RiskRecord],
    dimensions: DecisionDimensions,
) -> float:
    if blocking:
        return 0.45
    base = {
        StrategyPosture.OFFICIAL_REPOSITORY: 0.9,
        StrategyPosture.HYBRID: 0.72,
        StrategyPosture.GREENFIELD: 0.52,
    }.get(strategy.primary_posture, 0.6)
    if readiness.execution_ready == ReadinessLevel.PARTIAL:
        base -= 0.08
    elif readiness.execution_ready == ReadinessLevel.NOT_READY:
        base -= 0.2
    base -= min(0.15, 0.03 * len(degraded))
    if dimensions.resource_reliability == DimensionLevel.LOW:
        base -= 0.05
    return max(0.35, min(0.95, round(base, 2)))


def _artifact_status_hint(
    blocking: list[RiskRecord],
    degraded: list[RiskRecord],
    confidence: float,
) -> PlanningStatus:
    if blocking:
        return PlanningStatus.DEGRADED
    if degraded:
        return PlanningStatus.PARTIAL
    if confidence >= 0.85:
        return PlanningStatus.COMPLETE
    return PlanningStatus.PARTIAL


def _assessment_rationale(
    strategy: StrategyDecisionSnapshot,
    readiness: ExecutionReadiness,
    blocking: list[RiskRecord],
    degraded: list[RiskRecord],
) -> str:
    return (
        f"Risk assessment for {strategy.primary_posture.value} posture: "
        f"execution_ready={readiness.execution_ready.value}, "
        f"blocking_risks={len(blocking)}, degraded_risks={len(degraded)}."
    )


def _diagnostics(
    strategy: StrategyDecisionSnapshot,
    reuse_plan: ReusePlanSnapshot,
    readiness: ExecutionReadiness,
    confidence: float,
    blocking: list[RiskRecord],
    degraded: list[RiskRecord],
    informational: list[RiskRecord],
) -> dict[str, str]:
    return {
        "posture": strategy.primary_posture.value,
        "reuse_mode": reuse_plan.reuse_mode.value,
        "resource_ready": readiness.resource_ready.value,
        "engineering_ready": readiness.engineering_ready.value,
        "dependency_ready": readiness.dependency_ready.value,
        "execution_ready": readiness.execution_ready.value,
        "confidence": confidence_string(confidence),
        "blocking_risk_count": str(len(blocking)),
        "degraded_risk_count": str(len(degraded)),
        "informational_risk_count": str(len(informational)),
    }


def _provider_factors(
    dimensions: DecisionDimensions,
    readiness: ExecutionReadiness,
    blocking_count: int,
    degraded_count: int,
) -> tuple[str, ...]:
    return (
        provider_name_factor(_PROVIDER_NAME),
        f"execution_ready:{readiness.execution_ready.value}",
        f"blocking_risks:{blocking_count}",
        f"degraded_risks:{degraded_count}",
        dimension_factor("resource_sufficiency", dimensions.resource_sufficiency),
        dimension_factor("resource_reliability", dimensions.resource_reliability),
    )
