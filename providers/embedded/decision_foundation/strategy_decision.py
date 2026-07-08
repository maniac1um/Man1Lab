"""Strategy engineering decision from facts and dimensions."""

from __future__ import annotations

from dataclasses import dataclass

from models.execution_strategy import (
    PlanningStatus,
    RejectedPosture,
    ScopeCommitment,
    StrategyPosture,
)
from providers.embedded.decision_foundation.common import provider_name_factor, standard_dimension_factors
from providers.embedded.decision_foundation.dimensions import DecisionDimensions, DimensionLevel
from providers.embedded.decision_foundation.facts import ObservedFacts

RULE_REUSE = "rule:reuse"
RULE_HYBRID = "rule:hybrid"
RULE_GREENFIELD = "rule:greenfield"


@dataclass(frozen=True)
class StrategyDecision:
    primary_posture: StrategyPosture
    scope_commitment: ScopeCommitment
    scope_narrowing_rationale: str | None
    rationale: str
    rule_factor: str
    invocation_factor: str
    deciding_factors: tuple[str, ...]
    confidence: float
    alternative_postures_rejected: tuple[RejectedPosture, ...]
    artifact_status_hint: PlanningStatus
    decision_notes: tuple[str, ...]


def decide_strategy(facts: ObservedFacts, dimensions: DecisionDimensions) -> StrategyDecision:
    if _rule_reuse_applies(facts, dimensions):
        return StrategyDecision(
            primary_posture=StrategyPosture.OFFICIAL_REPOSITORY,
            scope_commitment=ScopeCommitment.NARROWED_SCOPE,
            scope_narrowing_rationale=(
                "Reuse verified official repository with minimal additional implementation scope."
            ),
            rationale="Verified official implementation satisfies required resources.",
            rule_factor=RULE_REUSE,
            invocation_factor="invocation_reason:discovery_complete",
            deciding_factors=_dimension_factors(dimensions, RULE_REUSE),
            confidence=0.9,
            alternative_postures_rejected=(
                RejectedPosture(
                    posture=StrategyPosture.HYBRID,
                    rejection_reason="Official repository verified with no required resource gaps.",
                ),
                RejectedPosture(
                    posture=StrategyPosture.GREENFIELD,
                    rejection_reason="Verified official repository available.",
                ),
            ),
            artifact_status_hint=PlanningStatus.COMPLETE,
            decision_notes=_strategy_notes(facts, StrategyPosture.OFFICIAL_REPOSITORY),
        )

    if _rule_hybrid_applies(facts, dimensions):
        return StrategyDecision(
            primary_posture=StrategyPosture.HYBRID,
            scope_commitment=ScopeCommitment.PARTIAL_REPRODUCTION,
            scope_narrowing_rationale=None,
            rationale="Repository available but required artifacts remain unavailable.",
            rule_factor=RULE_HYBRID,
            invocation_factor="invocation_reason:discovery_partial",
            deciding_factors=_dimension_factors(dimensions, RULE_HYBRID),
            confidence=0.75,
            alternative_postures_rejected=(
                RejectedPosture(
                    posture=StrategyPosture.OFFICIAL_REPOSITORY,
                    rejection_reason="Required discovery gaps prevent full reuse posture.",
                ),
                RejectedPosture(
                    posture=StrategyPosture.GREENFIELD,
                    rejection_reason="A reusable repository candidate is available.",
                ),
            ),
            artifact_status_hint=PlanningStatus.PARTIAL,
            decision_notes=_strategy_notes(facts, StrategyPosture.HYBRID),
        )

    return StrategyDecision(
        primary_posture=StrategyPosture.GREENFIELD,
        scope_commitment=ScopeCommitment.FULL_REPRODUCTION,
        scope_narrowing_rationale=None,
        rationale="No verified reusable implementation was discovered.",
        rule_factor=RULE_GREENFIELD,
        invocation_factor="invocation_reason:insufficient_discovery",
        deciding_factors=_dimension_factors(dimensions, RULE_GREENFIELD),
        confidence=0.5,
        alternative_postures_rejected=(
            RejectedPosture(
                posture=StrategyPosture.OFFICIAL_REPOSITORY,
                rejection_reason="No verified official repository selection.",
            ),
            RejectedPosture(
                posture=StrategyPosture.HYBRID,
                rejection_reason="No partially reusable repository selection.",
            ),
        ),
        artifact_status_hint=PlanningStatus.PARTIAL,
        decision_notes=_strategy_notes(facts, StrategyPosture.GREENFIELD),
    )


def _rule_reuse_applies(facts: ObservedFacts, dimensions: DecisionDimensions) -> bool:
    return (
        facts.repository_official
        and facts.repository_verified
        and not facts.required_resource_gaps
        and dimensions.reuse_opportunity == DimensionLevel.HIGH
        and dimensions.resource_sufficiency == DimensionLevel.HIGH
    )


def _rule_hybrid_applies(facts: ObservedFacts, dimensions: DecisionDimensions) -> bool:
    return (
        facts.repository_usable
        and bool(facts.required_resource_gaps)
        and dimensions.adaptation_requirement == DimensionLevel.HIGH
    )


def _dimension_factors(dimensions: DecisionDimensions, rule_factor: str) -> tuple[str, ...]:
    return (
        provider_name_factor("embedded_strategy"),
        rule_factor,
        *standard_dimension_factors(dimensions),
        _invocation_reason_factor(rule_factor),
    )


def _invocation_reason_factor(rule_factor: str) -> str:
    if rule_factor == RULE_REUSE:
        return "invocation_reason:discovery_complete"
    if rule_factor == RULE_HYBRID:
        return "invocation_reason:discovery_partial"
    return "invocation_reason:insufficient_discovery"


def _strategy_notes(facts: ObservedFacts, posture: StrategyPosture) -> tuple[str, ...]:
    notes: list[str] = []
    if facts.selected_repository is not None:
        notes.append(f"Repository candidate detected: {facts.selected_repository.candidate_id}")
        status = facts.selected_repository.verification_status
        notes.append(f"Verification status: {status.value if status else 'none'}")
    else:
        notes.append("No usable repository selection detected")
    if facts.required_resource_gaps:
        for gap in facts.required_resource_gaps:
            notes.append(f"Required gap: {gap.gap_type.value} ({gap.severity.value})")
    else:
        notes.append("Required resource gaps: none")
    notes.append(f"Selected {posture.value.upper()} posture")
    return tuple(notes)
