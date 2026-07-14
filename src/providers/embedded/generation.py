"""Deterministic generation planning via shared decision foundation."""

from __future__ import annotations

from datetime import UTC, datetime

from models.execution_planning_runtime import (
    AdaptationPlanResult,
    GenerationPlanResult,
    GenerationPlanSnapshot,
    StageRuntimeStatus,
)
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from providers.embedded.decision_foundation.dimensions import evaluate_dimensions
from providers.embedded.decision_foundation.facts import build_observed_facts
from providers.embedded.decision_foundation.generation_decision import decide_generation


class EmbeddedGenerationProvider:
    """Plan engineering artifact generation from prior stages — no network, no LLM."""

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        adaptation_result: AdaptationPlanResult,
    ) -> GenerationPlanResult:
        started_at = datetime.now(UTC)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        decision = decide_generation(
            facts,
            dimensions,
            adaptation_result.strategy,
            adaptation_result.resource_bindings,
            adaptation_result.reuse_plan,
            adaptation_result.adaptation_plan,
        )

        if decision.generation_required and decision.modules_to_generate:
            stage_status = StageRuntimeStatus.SUCCESS
        elif decision.generation_required:
            stage_status = StageRuntimeStatus.PARTIAL
        else:
            stage_status = StageRuntimeStatus.SUCCESS

        completed_at = datetime.now(UTC)
        return GenerationPlanResult(
            started_at=started_at,
            completed_at=completed_at,
            stage_status=stage_status,
            decision_notes="\n".join((decision.generation_rationale, *decision.decision_notes)),
            warnings=list(decision.warnings),
            diagnostics=decision.diagnostics,
            strategy=adaptation_result.strategy,
            resource_bindings=adaptation_result.resource_bindings,
            reuse_plan=adaptation_result.reuse_plan,
            adaptation_plan=adaptation_result.adaptation_plan,
            generation_plan=GenerationPlanSnapshot(
                generation_required=decision.generation_required,
                generation_scope=decision.generation_scope,
                modules_to_generate=list(decision.modules_to_generate),
                generation_constraints=list(decision.generation_constraints),
                generation_rationale=decision.generation_rationale,
                reuse_fallback_after_generation=decision.reuse_fallback_after_generation,
            ),
        )
