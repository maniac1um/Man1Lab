"""Deterministic risk assessment via shared decision foundation."""

from __future__ import annotations

from datetime import UTC, datetime

from models.execution_planning_runtime import (
    GenerationPlanResult,
    RiskAssessmentResult,
    RiskAssessmentSnapshot,
    StageRuntimeStatus,
)
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from providers.embedded.decision_foundation.dimensions import evaluate_dimensions
from providers.embedded.decision_foundation.facts import build_observed_facts
from providers.embedded.decision_foundation.risk_decision import decide_risk, evaluate_execution_readiness


class EmbeddedRiskProvider:
    """Evaluate execution readiness and residual risks — no network, no LLM."""

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        generation_result: GenerationPlanResult,
    ) -> RiskAssessmentResult:
        started_at = datetime.now(UTC)
        facts = build_observed_facts(analysis, discovery)
        dimensions = evaluate_dimensions(facts)
        readiness = evaluate_execution_readiness(
            facts,
            dimensions,
            generation_result.strategy,
            generation_result.resource_bindings,
            generation_result.reuse_plan,
            generation_result.adaptation_plan,
            generation_result.generation_plan,
        )
        decision = decide_risk(
            facts,
            dimensions,
            readiness,
            generation_result.strategy,
            generation_result.resource_bindings,
            generation_result.reuse_plan,
            generation_result.adaptation_plan,
            generation_result.generation_plan,
        )

        if decision.blocking_risks:
            stage_status = StageRuntimeStatus.DEGRADED
        elif decision.degraded_risks:
            stage_status = StageRuntimeStatus.PARTIAL
        else:
            stage_status = StageRuntimeStatus.SUCCESS

        completed_at = datetime.now(UTC)
        return RiskAssessmentResult(
            started_at=started_at,
            completed_at=completed_at,
            stage_status=stage_status,
            decision_notes="\n".join((decision.assessment_rationale, *decision.decision_notes)),
            warnings=list(decision.warnings),
            diagnostics=decision.diagnostics,
            strategy=generation_result.strategy,
            resource_bindings=generation_result.resource_bindings,
            reuse_plan=generation_result.reuse_plan,
            adaptation_plan=generation_result.adaptation_plan,
            generation_plan=generation_result.generation_plan,
            risk_assessment=RiskAssessmentSnapshot(
                overall_confidence=decision.overall_confidence,
                blocking_risks=list(decision.blocking_risks),
                degraded_risks=list(decision.degraded_risks),
                informational_risks=list(decision.informational_risks),
                fallback_strategies=list(decision.fallback_strategies),
                accepted_discovery_gap_ids=list(decision.accepted_discovery_gap_ids),
                manual_actions_required=list(decision.manual_actions_required),
                abort_conditions=list(decision.abort_conditions),
                artifact_status_hint=decision.artifact_status_hint,
            ),
        )
