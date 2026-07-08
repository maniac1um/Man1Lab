"""Deterministic adaptation planning via shared decision foundation."""

from __future__ import annotations

from datetime import UTC, datetime

from models.execution_planning_runtime import (
    AdaptationPlanResult,
    AdaptationPlanSnapshot,
    ReusePlanResult,
    StageRuntimeStatus,
)
from models.execution_strategy import AdaptationScope, ReuseMode, StrategyPosture
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from providers.embedded.decision_foundation.adaptation_decision import decide_adaptation
from providers.embedded.decision_foundation.dimensions import evaluate_dimensions
from providers.embedded.decision_foundation.facts import build_observed_facts


class EmbeddedAdaptationProvider:
    """Authorize adaptation scope from reuse and decision foundation — no network, no LLM."""

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        reuse_result: ReusePlanResult,
    ) -> AdaptationPlanResult:
        started_at = datetime.now(UTC)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_adaptation(
            facts,
            dimensions,
            reuse_result.strategy,
            reuse_result.resource_bindings,
            reuse_result.reuse_plan,
        )

        if reuse_result.strategy.primary_posture == StrategyPosture.GREENFIELD:
            stage_status = StageRuntimeStatus.SUCCESS
        elif decision.adaptation_required and decision.authorized_modifications:
            stage_status = StageRuntimeStatus.SUCCESS
        elif decision.adaptation_required:
            stage_status = StageRuntimeStatus.PARTIAL
        else:
            stage_status = StageRuntimeStatus.SUCCESS

        completed_at = datetime.now(UTC)
        return AdaptationPlanResult(
            started_at=started_at,
            completed_at=completed_at,
            stage_status=stage_status,
            decision_notes="\n".join((decision.adaptation_rationale, *decision.decision_notes)),
            warnings=list(decision.warnings),
            diagnostics=decision.diagnostics,
            strategy=reuse_result.strategy,
            resource_bindings=reuse_result.resource_bindings,
            reuse_plan=reuse_result.reuse_plan,
            adaptation_plan=AdaptationPlanSnapshot(
                adaptation_required=decision.adaptation_required,
                adaptation_scope=decision.adaptation_scope,
                authorized_modifications=list(decision.authorized_modifications),
                adaptation_constraints=list(decision.adaptation_constraints),
                adaptation_triggers=list(decision.adaptation_triggers),
                adaptation_deferred=decision.adaptation_deferred,
            ),
        )
