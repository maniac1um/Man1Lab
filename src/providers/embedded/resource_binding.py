"""Deterministic resource binding via shared decision foundation."""

from __future__ import annotations

from datetime import UTC, datetime

from models.execution_planning_runtime import (
    ResourceBindingResult,
    ResourceBindingSnapshot,
    StageRuntimeStatus,
    StrategyDecisionResult,
)
from models.execution_strategy import StrategyPosture
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from providers.embedded.decision_foundation.binding_decision import decide_bindings
from providers.embedded.decision_foundation.dimensions import evaluate_dimensions
from providers.embedded.decision_foundation.facts import build_observed_facts


class EmbeddedResourceBindingProvider:
    """Bind verified discovery selections to execution roles — no network, no LLM."""

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        strategy_result: StrategyDecisionResult,
    ) -> ResourceBindingResult:
        started_at = datetime.now(UTC)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_bindings(facts, dimensions, strategy_result.strategy)

        posture = strategy_result.strategy.primary_posture
        if posture == StrategyPosture.GREENFIELD:
            stage_status = StageRuntimeStatus.SUCCESS
        elif decision.bindings:
            stage_status = StageRuntimeStatus.SUCCESS
        else:
            stage_status = StageRuntimeStatus.PARTIAL

        completed_at = datetime.now(UTC)
        return ResourceBindingResult(
            started_at=started_at,
            completed_at=completed_at,
            stage_status=stage_status,
            decision_notes=decision.decision_notes,
            warnings=list(decision.warnings),
            diagnostics=decision.diagnostics,
            strategy=strategy_result.strategy,
            resource_bindings=ResourceBindingSnapshot(
                bindings=list(decision.bindings),
                anchor_binding_id=decision.anchor_binding_id,
                combination_rationale=decision.combination_rationale,
                selection_alignment_summary=decision.selection_alignment_summary,
            ),
        )
