"""Deterministic reuse planning via shared decision foundation."""

from __future__ import annotations

from datetime import UTC, datetime

from models.execution_planning_runtime import (
    ResourceBindingResult,
    ReusePlanResult,
    ReusePlanSnapshot,
    StageRuntimeStatus,
)
from models.execution_strategy import ReuseMode, StrategyPosture
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from providers.embedded.decision_foundation.dimensions import evaluate_dimensions
from providers.embedded.decision_foundation.facts import build_observed_facts
from providers.embedded.decision_foundation.reuse_decision import decide_reuse


class EmbeddedReuseProvider:
    """Decide reuse commitments from bindings and decision foundation — no network, no LLM."""

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        binding_result: ResourceBindingResult,
    ) -> ReusePlanResult:
        started_at = datetime.now(UTC)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_reuse(
            facts,
            dimensions,
            binding_result.resource_bindings,
            binding_result.strategy,
        )

        if decision.reuse_mode == ReuseMode.NOT_APPLICABLE:
            stage_status = StageRuntimeStatus.SUCCESS
        elif decision.components_to_reuse:
            stage_status = StageRuntimeStatus.SUCCESS
        else:
            stage_status = StageRuntimeStatus.PARTIAL

        completed_at = datetime.now(UTC)
        return ReusePlanResult(
            started_at=started_at,
            completed_at=completed_at,
            stage_status=stage_status,
            decision_notes="\n".join(decision.decision_notes),
            warnings=list(decision.warnings),
            diagnostics=decision.diagnostics,
            strategy=binding_result.strategy,
            resource_bindings=binding_result.resource_bindings,
            reuse_plan=ReusePlanSnapshot(
                reuse_mode=decision.reuse_mode,
                primary_reuse_binding_id=decision.primary_reuse_binding_id,
                components_to_reuse=list(decision.components_to_reuse),
                components_excluded=list(decision.components_excluded),
                reuse_assumptions=list(decision.reuse_assumptions),
                reuse_limitations=list(decision.reuse_limitations),
            ),
        )
