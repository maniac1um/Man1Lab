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
RULE_OFFICIAL_USABLE = "rule:official_usable"
RULE_COMMUNITY = "rule:community"
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

    if _rule_official_usable_applies(facts, dimensions):
        return StrategyDecision(
            primary_posture=StrategyPosture.OFFICIAL_REPOSITORY,
            scope_commitment=ScopeCommitment.NARROWED_SCOPE,
            scope_narrowing_rationale=(
                "Official repository selected with partial verification; adaptation may be required."
            ),
            rationale=(
                "Official repository discovered and selected; proceeding with narrowed scope "
                "pending full verification."
            ),
            rule_factor=RULE_OFFICIAL_USABLE,
            invocation_factor="invocation_reason:discovery_partial",
            deciding_factors=_dimension_factors(dimensions, RULE_OFFICIAL_USABLE),
            confidence=0.72,
            alternative_postures_rejected=(
                RejectedPosture(
                    posture=StrategyPosture.GREENFIELD,
                    rejection_reason="Official repository selection exists and is usable.",
                ),
                RejectedPosture(
                    posture=StrategyPosture.HYBRID,
                    rejection_reason="No required resource gaps block official repository posture.",
                ),
            ),
            artifact_status_hint=PlanningStatus.PARTIAL,
            decision_notes=_strategy_notes(facts, StrategyPosture.OFFICIAL_REPOSITORY),
        )

    if _rule_community_applies(facts, dimensions):
        return StrategyDecision(
            primary_posture=StrategyPosture.COMMUNITY_FORK,
            scope_commitment=ScopeCommitment.PARTIAL_REPRODUCTION,
            scope_narrowing_rationale=None,
            rationale="Verified community repository selected for fork-based reproduction.",
            rule_factor=RULE_COMMUNITY,
            invocation_factor="invocation_reason:discovery_complete",
            deciding_factors=_dimension_factors(dimensions, RULE_COMMUNITY),
            confidence=0.78,
            alternative_postures_rejected=(
                RejectedPosture(
                    posture=StrategyPosture.OFFICIAL_REPOSITORY,
                    rejection_reason="Selected repository is community, not official.",
                ),
                RejectedPosture(
                    posture=StrategyPosture.GREENFIELD,
                    rejection_reason="Verified community repository available.",
                ),
            ),
            artifact_status_hint=PlanningStatus.COMPLETE,
            decision_notes=_strategy_notes(facts, StrategyPosture.COMMUNITY_FORK),
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


def _rule_official_usable_applies(facts: ObservedFacts, dimensions: DecisionDimensions) -> bool:
    return (
        facts.repository_official
        and facts.repository_usable
        and not facts.repository_verified
        and not facts.required_resource_gaps
        and dimensions.resource_sufficiency != DimensionLevel.LOW
    )


def _rule_community_applies(facts: ObservedFacts, dimensions: DecisionDimensions) -> bool:
    return (
        facts.repository_available
        and not facts.repository_official
        and facts.repository_verified
        and not facts.required_resource_gaps
        and dimensions.reuse_opportunity in {DimensionLevel.HIGH, DimensionLevel.MEDIUM}
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
    if rule_factor in {RULE_REUSE, RULE_COMMUNITY}:
        return "invocation_reason:discovery_complete"
    if rule_factor in {RULE_HYBRID, RULE_OFFICIAL_USABLE}:
        return "invocation_reason:discovery_partial"
    return "invocation_reason:insufficient_discovery"


def _strategy_notes(facts: ObservedFacts, posture: StrategyPosture) -> tuple[str, ...]:
    notes: list[str] = []
    if facts.selected_repository is not None:
        notes.append(f"Repository candidate detected: {facts.selected_repository.candidate_id}")
        status = facts.selected_repository.verification_status
        notes.append(f"Verification status: {status.value if status else 'none'}")
        if facts.selected_repository.selection_confidence > 0:
            notes.append(
                f"Discovery selection confidence: {facts.selected_repository.selection_confidence:.2f}"
            )
        for contribution in facts.selected_repository.confidence_composition.contributions:
            if contribution.contribution > 0:
                notes.append(f"Confidence signal {contribution.signal}: {contribution.contribution:.2f}")
    else:
        notes.append("No usable repository selection detected")
    for asset in facts.selected_assets:
        if asset.asset_type is not None:
            notes.append(f"Selected {asset.asset_type.value} asset: {asset.candidate_id}")
    if facts.required_resource_gaps:
        for gap in facts.required_resource_gaps:
            notes.append(f"Required gap: {gap.gap_type.value} ({gap.severity.value})")
    else:
        notes.append("Required resource gaps: none")
    notes.append(f"Selected {posture.value.upper()} posture")
    return tuple(notes)
