"""Assemble canonical ExecutionStrategy from cumulative runtime stage results."""

from __future__ import annotations

from datetime import UTC, datetime

from models.execution_planning_runtime import (
    AdaptationPlanSnapshot,
    GenerationPlanSnapshot,
    ResourceBindingSnapshot,
    ReusePlanSnapshot,
    RiskAssessmentResult,
    RiskAssessmentSnapshot,
    StrategyDecisionSnapshot,
)
from models.execution_strategy import (
    SCHEMA_VERSION,
    ExecutionStrategy,
    InputReferences,
    PlanningInvocationReason,
    Provenance,
    StrategyPosture,
)
from validation.execution_strategy import (
    build_execution_strategy,
    normalize_execution_strategy,
    validate_execution_strategy,
)


class ExecutionStrategyBuilder:
    """Deterministic assembly from RiskAssessmentResult to ExecutionStrategy.

    The builder performs no engineering reasoning. It maps runtime snapshots to
    canonical modules, injects schema version and required metadata defaults,
    and delegates structural validation to the validation layer.
    """

    @staticmethod
    def build(
        risk_result: RiskAssessmentResult,
        *,
        strategy_id: str,
        input_references: InputReferences,
        created_at: datetime | None = None,
        summary: str = "",
        invocation_reason: PlanningInvocationReason = PlanningInvocationReason.DISCOVERY_COMPLETE,
        reproduction_scope: str = "",
        provenance: Provenance | None = None,
    ) -> ExecutionStrategy:
        """Assemble and validate an ExecutionStrategy from the final runtime result."""
        candidate = _assemble_candidate(
            risk_result,
            strategy_id=strategy_id,
            input_references=input_references,
            created_at=created_at,
            summary=summary,
            invocation_reason=invocation_reason,
            reproduction_scope=reproduction_scope,
            provenance=provenance or Provenance(),
        )
        normalized = normalize_execution_strategy(candidate)
        validate_execution_strategy(normalized)
        return build_execution_strategy(normalized)


def _assemble_candidate(
    risk_result: RiskAssessmentResult,
    *,
    strategy_id: str,
    input_references: InputReferences,
    created_at: datetime | None,
    summary: str,
    invocation_reason: PlanningInvocationReason,
    reproduction_scope: str,
    provenance: Provenance,
) -> dict:
    resolved_created_at = created_at or datetime.now(UTC)
    scope = reproduction_scope or input_references.analysis_reference.reproduction_scope

    return {
        "schema_version": SCHEMA_VERSION,
        "metadata": _assemble_metadata(
            risk_result,
            strategy_id=strategy_id,
            created_at=resolved_created_at,
            summary=summary,
            invocation_reason=invocation_reason,
            reproduction_scope=scope,
        ),
        "input_references": input_references.model_dump(mode="json"),
        "strategy": _map_strategy_snapshot(risk_result.strategy),
        "resource_bindings": _map_resource_bindings_snapshot(risk_result.resource_bindings),
        "reuse_plan": _map_reuse_plan_snapshot(risk_result.reuse_plan),
        "adaptation_plan": _map_adaptation_plan_snapshot(risk_result.adaptation_plan),
        "generation_plan": _map_generation_plan_snapshot(risk_result.generation_plan),
        "risk_assessment": _map_risk_assessment_snapshot(risk_result.risk_assessment),
        "provenance": provenance.model_dump(mode="json"),
    }


def _assemble_metadata(
    risk_result: RiskAssessmentResult,
    *,
    strategy_id: str,
    created_at: datetime,
    summary: str,
    invocation_reason: PlanningInvocationReason,
    reproduction_scope: str,
) -> dict:
    bindings = risk_result.resource_bindings.bindings
    blocking_risks = risk_result.risk_assessment.blocking_risks
    manual_actions = risk_result.risk_assessment.manual_actions_required
    posture = risk_result.strategy.primary_posture

    return {
        "strategy_id": strategy_id,
        "created_at": created_at.isoformat(),
        "status": risk_result.risk_assessment.artifact_status_hint.value,
        "summary": summary,
        "reproduction_scope": reproduction_scope,
        "invocation_reason": invocation_reason.value,
        "strategy_posture": posture.value,
        "binding_count": len(bindings),
        "blocking_risk_count": len(blocking_risks),
        "manual_action_required": posture == StrategyPosture.MANUAL or bool(manual_actions),
    }


def _map_strategy_snapshot(snapshot: StrategyDecisionSnapshot) -> dict:
    return snapshot.model_dump(mode="json", exclude={"artifact_status_hint"})


def _map_resource_bindings_snapshot(snapshot: ResourceBindingSnapshot) -> dict:
    return snapshot.model_dump(mode="json", exclude={"selection_alignment_summary"})


def _map_reuse_plan_snapshot(snapshot: ReusePlanSnapshot) -> dict:
    return snapshot.model_dump(mode="json")


def _map_adaptation_plan_snapshot(snapshot: AdaptationPlanSnapshot) -> dict:
    return snapshot.model_dump(mode="json")


def _map_generation_plan_snapshot(snapshot: GenerationPlanSnapshot) -> dict:
    return snapshot.model_dump(mode="json")


def _map_risk_assessment_snapshot(snapshot: RiskAssessmentSnapshot) -> dict:
    return snapshot.model_dump(mode="json", exclude={"artifact_status_hint"})
