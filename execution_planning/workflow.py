"""Execution Planning workflow coordinator — orchestration only."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Type

from execution_planning.builder import ExecutionStrategyBuilder
from models.execution_planning_runtime import ResourceBindingResult
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
from services.execution_planning.adaptation_service import AdaptationService
from services.execution_planning.generation_service import GenerationService
from services.execution_planning.resource_binding_service import ResourceBindingService
from services.execution_planning.reuse_service import ReuseService
from services.execution_planning.risk_service import RiskService
from services.execution_planning.strategy_service import StrategyService


class ExecutionPlanningWorkflow:
    """Execution Planning coordinator — six fixed stages, then builder assembly."""

    def __init__(
        self,
        strategy_service: StrategyService,
        resource_binding_service: ResourceBindingService,
        reuse_service: ReuseService,
        adaptation_service: AdaptationService,
        generation_service: GenerationService,
        risk_service: RiskService,
        builder: Type[ExecutionStrategyBuilder] = ExecutionStrategyBuilder,
        *,
        pipeline_version: str = "1.2.0",
    ) -> None:
        self._strategy_service = strategy_service
        self._resource_binding_service = resource_binding_service
        self._reuse_service = reuse_service
        self._adaptation_service = adaptation_service
        self._generation_service = generation_service
        self._risk_service = risk_service
        self._builder = builder
        self._pipeline_version = pipeline_version

    def run(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
    ) -> ExecutionStrategy:
        timestamps: dict[str, datetime] = {}

        timestamps["strategy_decision"] = datetime.now(UTC)
        strategy_result = self._strategy_service.execute(analysis, discovery)

        timestamps["resource_binding"] = datetime.now(UTC)
        binding_result = self._resource_binding_service.execute(
            analysis,
            discovery,
            strategy_result,
        )

        timestamps["reuse_planning"] = datetime.now(UTC)
        reuse_result = self._reuse_service.execute(analysis, discovery, binding_result)

        timestamps["adaptation_planning"] = datetime.now(UTC)
        adaptation_result = self._adaptation_service.execute(analysis, discovery, reuse_result)

        timestamps["generation_planning"] = datetime.now(UTC)
        generation_result = self._generation_service.execute(analysis, discovery, adaptation_result)

        timestamps["risk_assessment"] = datetime.now(UTC)
        risk_result = self._risk_service.execute(analysis, discovery, generation_result)

        timestamps["assembly"] = datetime.now(UTC)
        planning_run_id = str(uuid.uuid4())
        invocation_reason = _invocation_reason(discovery)
        input_references = _build_input_references(analysis, discovery, binding_result)

        return self._builder.build(
            risk_result,
            strategy_id=_new_strategy_id(),
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
        return cls(
            strategy_service=StrategyService.default(),
            resource_binding_service=ResourceBindingService.default(),
            reuse_service=ReuseService.default(),
            adaptation_service=AdaptationService.default(),
            generation_service=GenerationService.default(),
            risk_service=RiskService.default(),
        )


def _build_input_references(
    analysis: PaperReproductionAnalysis,
    discovery: ResearchResourceDiscovery,
    binding_result: ResourceBindingResult,
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


def _new_strategy_id() -> str:
    return f"strategy-{uuid.uuid4()}"
