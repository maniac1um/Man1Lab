"""Execution Planning workflow coordinator."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from execution_planning.builder import ExecutionStrategyBuilder
from execution_planning.stages import (
    new_strategy_id,
    run_adaptation_planning,
    run_generation_planning,
    run_resource_binding,
    run_reuse_planning,
    run_risk_assessment,
    run_strategy_decision,
)
from models.execution_strategy import (
    AnalysisReference,
    DecisionCategory,
    DecisionRecord,
    DiscoveryReference,
    ExecutionStrategy,
    InputReferences,
    PlanningInvocationReason,
    Provenance,
)
from models.paper_reproduction_analysis import (
    SCHEMA_VERSION as ANALYSIS_SCHEMA_VERSION,
    PaperReproductionAnalysis,
)
from models.research_resource_discovery import ResearchResourceDiscovery


class ExecutionPlanningWorkflow:
    """Run six fixed planning stages and assemble ExecutionStrategy."""

    def __init__(self, *, pipeline_version: str = "1.2.0") -> None:
        self._pipeline_version = pipeline_version

    def run(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
    ) -> ExecutionStrategy:
        timestamps: dict[str, datetime] = {}
        now = datetime.now(UTC)

        timestamps["strategy_decision"] = now
        strategy_result = run_strategy_decision(analysis, discovery, started_at=now)

        timestamps["resource_binding"] = datetime.now(UTC)
        binding_result = run_resource_binding(
            analysis,
            discovery,
            strategy_result,
            started_at=timestamps["resource_binding"],
        )

        timestamps["reuse_planning"] = datetime.now(UTC)
        reuse_result = run_reuse_planning(
            binding_result,
            started_at=timestamps["reuse_planning"],
        )

        timestamps["adaptation_planning"] = datetime.now(UTC)
        adaptation_result = run_adaptation_planning(
            discovery,
            reuse_result,
            started_at=timestamps["adaptation_planning"],
        )

        timestamps["generation_planning"] = datetime.now(UTC)
        generation_result = run_generation_planning(
            analysis,
            adaptation_result,
            started_at=timestamps["generation_planning"],
        )

        timestamps["risk_assessment"] = datetime.now(UTC)
        risk_result = run_risk_assessment(
            discovery,
            generation_result,
            started_at=timestamps["risk_assessment"],
        )

        timestamps["assembly"] = datetime.now(UTC)
        planning_run_id = str(uuid.uuid4())
        invocation_reason = _invocation_reason(discovery)
        input_references = _build_input_references(analysis, discovery, binding_result)

        return ExecutionStrategyBuilder.build(
            risk_result,
            strategy_id=new_strategy_id(),
            input_references=input_references,
            created_at=timestamps["assembly"],
            summary=risk_result.decision_notes or strategy_result.strategy.rationale,
            invocation_reason=invocation_reason,
            reproduction_scope=analysis.goal.scope.value if analysis.goal.scope else "",
            provenance=Provenance(
                planning_run_id=planning_run_id,
                pipeline_version=self._pipeline_version,
                stage_timestamps=timestamps,
                decision_trace=[
                    DecisionRecord(
                        decision_id="decision-strategy",
                        decision_category=DecisionCategory.RESOURCE,
                        summary=strategy_result.strategy.rationale,
                        inputs_consulted=["analysis", "discovery"],
                        timestamp=timestamps["strategy_decision"],
                    ),
                    DecisionRecord(
                        decision_id="decision-risk",
                        decision_category=DecisionCategory.RISK,
                        summary=risk_result.decision_notes,
                        inputs_consulted=["discovery.discovery_gaps"],
                        timestamp=timestamps["risk_assessment"],
                    ),
                ],
            ),
        )

    @classmethod
    def default(cls) -> ExecutionPlanningWorkflow:
        return cls()


def _build_input_references(
    analysis: PaperReproductionAnalysis,
    discovery: ResearchResourceDiscovery,
    binding_result,
) -> InputReferences:
    selection_ids = [
        binding.selection_id
        for binding in binding_result.resource_bindings.bindings
        if binding.selection_id
    ]
    return InputReferences(
        analysis_reference=AnalysisReference(
            analysis_schema_version=analysis.schema_version or ANALYSIS_SCHEMA_VERSION,
            paper_title=analysis.metadata.title,
            arxiv_id=analysis.metadata.arxiv_id or "",
            analysis_content_hash=_analysis_content_hash(analysis),
            reproduction_scope=analysis.goal.scope.value if analysis.goal.scope else "unknown",
            analysis_gap_categories=[gap.category.value for gap in analysis.reproduction_gaps],
        ),
        discovery_reference=DiscoveryReference(
            discovery_schema_version=discovery.schema_version,
            discovery_id=discovery.metadata.discovery_id,
            discovery_content_hash=_discovery_content_hash(discovery),
            discovery_status=discovery.metadata.status,
            selection_ids_used=sorted(set(selection_ids)),
            unresolved_discovery_gap_count=len(discovery.discovery_gaps.gaps),
        ),
    )


def _analysis_content_hash(analysis: PaperReproductionAnalysis) -> str:
    payload = analysis.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _discovery_content_hash(discovery: ResearchResourceDiscovery) -> str:
    payload = discovery.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _invocation_reason(discovery: ResearchResourceDiscovery) -> PlanningInvocationReason:
    from models.research_resource_discovery import DiscoveryStatus

    if discovery.metadata.status == DiscoveryStatus.COMPLETE:
        return PlanningInvocationReason.DISCOVERY_COMPLETE
    return PlanningInvocationReason.DISCOVERY_PARTIAL
