"""Build complete decision trace including planning stages."""

from __future__ import annotations

from datetime import UTC, datetime

from models.decision_trace import DecisionStageName, DecisionStageRecord, DecisionTrace
from models.execution_strategy import ExecutionStrategy
from models.research_resource_discovery import ResearchResourceDiscovery
from discovery.decision_trace import build_discovery_decision_trace


def build_planning_decision_trace(
    discovery: ResearchResourceDiscovery,
    strategy: ExecutionStrategy,
    *,
    pipeline_version: str = "1.2.4",
) -> DecisionTrace:
    """Merge discovery trace with binding, reuse, generation, and risk stages."""
    base = build_discovery_decision_trace(discovery, pipeline_version=pipeline_version)
    timestamps = strategy.provenance.stage_timestamps
    bindings = strategy.resource_bindings.bindings

    planning_stages = [
        DecisionStageRecord(
            stage=DecisionStageName.BINDING,
            inputs={
                "posture": strategy.strategy.primary_posture.value,
                "selection_ids": ",".join(strategy.input_references.discovery_reference.selection_ids_used),
            },
            outputs={
                "binding_count": str(len(bindings)),
                "anchor_binding_id": strategy.resource_bindings.anchor_binding_id or "",
            },
            decision_rule="binding:posture_and_verification_gate",
            rationale=strategy.resource_bindings.combination_rationale
            or "Bind discovery selections to execution roles.",
            recorded_at=timestamps.get("resource_binding"),
        ),
        DecisionStageRecord(
            stage=DecisionStageName.REUSE,
            inputs={"binding_count": str(len(bindings))},
            outputs={"reuse_mode": strategy.reuse_plan.reuse_mode.value},
            decision_rule="reuse:posture_mapping",
            rationale="; ".join(strategy.reuse_plan.reuse_assumptions) or "Reuse plan from bindings.",
            recorded_at=timestamps.get("reuse_planning"),
        ),
        DecisionStageRecord(
            stage=DecisionStageName.GENERATION,
            inputs={"reuse_mode": strategy.reuse_plan.reuse_mode.value},
            outputs={
                "generation_required": str(strategy.generation_plan.generation_required).lower(),
                "generation_scope": strategy.generation_plan.generation_scope.value,
            },
            decision_rule="generation:gap_and_posture",
            rationale=strategy.generation_plan.generation_rationale or "Generation authorization.",
            recorded_at=timestamps.get("generation_planning"),
        ),
        DecisionStageRecord(
            stage=DecisionStageName.RISK,
            inputs={"posture": strategy.strategy.primary_posture.value},
            outputs={
                "blocking_risk_count": str(len(strategy.risk_assessment.blocking_risks)),
                "overall_confidence": f"{strategy.risk_assessment.overall_confidence:.2f}",
            },
            decision_rule="risk:readiness_assessment",
            rationale=strategy.metadata.summary or "Risk and readiness assessment.",
            recorded_at=timestamps.get("risk_assessment"),
        ),
    ]
    return base.model_copy(
        update={
            "strategy_id": strategy.metadata.strategy_id,
            "created_at": datetime.now(UTC),
            "stages": [*base.stages, *planning_stages],
        }
    )
