"""Deterministic strategy decision via shared decision foundation."""

from __future__ import annotations

from datetime import UTC, datetime

from models.execution_planning_runtime import (
    StageRuntimeStatus,
    StrategyDecisionResult,
    StrategyDecisionSnapshot,
)
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import DiscoveryStatus, ResearchResourceDiscovery
from providers.embedded.decision_foundation.dimensions import evaluate_dimensions
from providers.embedded.decision_foundation.facts import build_observed_facts
from providers.embedded.decision_foundation.strategy_decision import decide_strategy


class EmbeddedStrategyProvider:
    """Decide engineering posture from analysis and discovery only — no network, no LLM."""

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
    ) -> StrategyDecisionResult:
        started_at = datetime.now(UTC)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_strategy(facts, dimensions)

        warnings: list[str] = []
        if facts.discovery_status != DiscoveryStatus.COMPLETE:
            warnings.append(f"Discovery status is {facts.discovery_status.value}")

        completed_at = datetime.now(UTC)
        return StrategyDecisionResult(
            started_at=started_at,
            completed_at=completed_at,
            stage_status=StageRuntimeStatus.SUCCESS,
            decision_notes="\n".join(decision.decision_notes),
            warnings=warnings,
            diagnostics={
                "resource_sufficiency": dimensions.resource_sufficiency.value,
                "resource_reliability": dimensions.resource_reliability.value,
                "reuse_opportunity": dimensions.reuse_opportunity.value,
            },
            strategy=StrategyDecisionSnapshot(
                primary_posture=decision.primary_posture,
                scope_commitment=decision.scope_commitment,
                scope_narrowing_rationale=decision.scope_narrowing_rationale,
                rationale=decision.rationale,
                deciding_factors=list(decision.deciding_factors),
                confidence=decision.confidence,
                alternative_postures_rejected=list(decision.alternative_postures_rejected),
                artifact_status_hint=decision.artifact_status_hint,
            ),
        )
