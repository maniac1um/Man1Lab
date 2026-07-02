import copy
import json
import unittest
from datetime import UTC, datetime

from execution_planning.builder import ExecutionStrategyBuilder
from models.execution_planning_runtime import (
    AdaptationPlanResult,
    AdaptationPlanSnapshot,
    GenerationPlanResult,
    GenerationPlanSnapshot,
    ResourceBindingResult,
    ResourceBindingSnapshot,
    ReusePlanResult,
    ReusePlanSnapshot,
    RiskAssessmentResult,
    RiskAssessmentSnapshot,
    StageRuntimeStatus,
    StrategyDecisionResult,
    StrategyDecisionSnapshot,
)
from models.execution_strategy import (
    SCHEMA_VERSION,
    AdaptationScope,
    AnalysisModule,
    AnalysisReference,
    BindingRole,
    DecisionCategory,
    DecisionRecord,
    DiscoveryReference,
    GenerationIntent,
    GenerationPriority,
    GenerationScope,
    InputReferences,
    PlanningInvocationReason,
    PlanningStatus,
    Provenance,
    RejectedPosture,
    ResourceBinding,
    ReuseMode,
    RiskCategory,
    RiskRecord,
    RiskSeverity,
    ScopeCommitment,
    StrategyPosture,
    UsageIntent,
)
from models.research_resource_discovery import DiscoveryStatus
from validation.exceptions import ExecutionStrategyValidationError


def _strategy_snapshot(**overrides) -> StrategyDecisionSnapshot:
    base = StrategyDecisionSnapshot(
        primary_posture=StrategyPosture.OFFICIAL_REPOSITORY,
        scope_commitment=ScopeCommitment.FULL_REPRODUCTION,
        rationale="Use official repository selected by Discovery.",
        deciding_factors=["verification_pass"],
        confidence=0.9,
        artifact_status_hint=PlanningStatus.COMPLETE,
    )
    if overrides:
        return base.model_copy(update=overrides)
    return base


def _binding_snapshot(**overrides) -> ResourceBindingSnapshot:
    base = ResourceBindingSnapshot(
        bindings=[
            ResourceBinding(
                binding_id="binding-repo",
                candidate_id="candidate-repo",
                role=BindingRole.PRIMARY_REPOSITORY,
                usage_intent=UsageIntent.EXECUTE_DIRECTLY,
            )
        ],
        anchor_binding_id="binding-repo",
        combination_rationale="Single official repository.",
        selection_alignment_summary="Aligned with discovery primary selection.",
    )
    if overrides:
        return base.model_copy(update=overrides)
    return base


def _input_references() -> InputReferences:
    return InputReferences(
        analysis_reference=AnalysisReference(
            analysis_schema_version="1.0",
            paper_title="Test Paper",
            analysis_content_hash="analysis-hash",
            reproduction_scope="training",
        ),
        discovery_reference=DiscoveryReference(
            discovery_schema_version="1.0",
            discovery_id="disc-1",
            discovery_content_hash="discovery-hash",
            discovery_status=DiscoveryStatus.COMPLETE,
        ),
    )


def _minimal_risk_result(**overrides) -> RiskAssessmentResult:
    strategy = _strategy_snapshot()
    resource_bindings = _binding_snapshot()
    reuse_plan = ReusePlanSnapshot(reuse_mode=ReuseMode.AS_IS, primary_reuse_binding_id="binding-repo")
    adaptation_plan = AdaptationPlanSnapshot(adaptation_required=False)
    generation_plan = GenerationPlanSnapshot(
        generation_required=False,
        generation_scope=GenerationScope.NONE,
    )
    risk_assessment = RiskAssessmentSnapshot(
        overall_confidence=0.9,
        artifact_status_hint=PlanningStatus.COMPLETE,
    )
    base = RiskAssessmentResult(
        stage_status=StageRuntimeStatus.SUCCESS,
        decision_notes="Risk assessment complete.",
        strategy=strategy,
        resource_bindings=resource_bindings,
        reuse_plan=reuse_plan,
        adaptation_plan=adaptation_plan,
        generation_plan=generation_plan,
        risk_assessment=risk_assessment,
    )
    if overrides:
        return base.model_copy(update=overrides)
    return base


def _complete_risk_result() -> RiskAssessmentResult:
    return RiskAssessmentResult(
        started_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        completed_at=datetime(2026, 7, 3, 12, 5, tzinfo=UTC),
        stage_status=StageRuntimeStatus.DEGRADED,
        decision_notes="Recorded degraded risks after generation planning.",
        warnings=["Discovery partial."],
        diagnostics={"discovery_status": "partial"},
        strategy=_strategy_snapshot(
            alternative_postures_rejected=[
                RejectedPosture(
                    posture=StrategyPosture.GREENFIELD,
                    rejection_reason="Official repository available.",
                )
            ]
        ),
        resource_bindings=_binding_snapshot(),
        reuse_plan=ReusePlanSnapshot(
            reuse_mode=ReuseMode.AS_IS,
            primary_reuse_binding_id="binding-repo",
            reuse_assumptions=["Checkpoint matches paper weights."],
        ),
        adaptation_plan=AdaptationPlanSnapshot(
            adaptation_required=True,
            adaptation_scope=AdaptationScope.MINIMAL,
            adaptation_constraints=["Do not change model architecture."],
        ),
        generation_plan=GenerationPlanSnapshot(
            generation_required=True,
            generation_scope=GenerationScope.MISSING_MODULES,
            modules_to_generate=[
                {
                    "analysis_module": AnalysisModule.EVALUATION,
                    "generation_intent": GenerationIntent.STUB_FOR_INTEGRATION,
                    "priority": GenerationPriority.DEGRADED,
                }
            ],
            generation_rationale="Eval harness missing from repository.",
        ),
        risk_assessment=RiskAssessmentSnapshot(
            overall_confidence=0.75,
            degraded_risks=[
                RiskRecord(
                    risk_id="risk-1",
                    severity=RiskSeverity.DEGRADED,
                    category=RiskCategory.UNRESOLVED_RESOURCE,
                    description="Checkpoint unresolved.",
                    related_binding_id="binding-repo",
                )
            ],
            manual_actions_required=[
                {
                    "action_id": "action-1",
                    "description": "Upload checkpoint manually.",
                    "blocks_planner": False,
                }
            ],
            artifact_status_hint=PlanningStatus.DEGRADED,
        ),
    )


class ExecutionStrategyBuilderTest(unittest.TestCase):
    def test_minimal_build(self) -> None:
        created_at = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
        strategy = ExecutionStrategyBuilder.build(
            _minimal_risk_result(),
            strategy_id="strategy-1",
            input_references=_input_references(),
            created_at=created_at,
            summary="Official repo reuse.",
        )
        self.assertEqual(strategy.schema_version, SCHEMA_VERSION)
        self.assertEqual(strategy.metadata.strategy_id, "strategy-1")
        self.assertEqual(strategy.metadata.status, PlanningStatus.COMPLETE)
        self.assertEqual(strategy.metadata.binding_count, 1)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)
        self.assertEqual(strategy.resource_bindings.anchor_binding_id, "binding-repo")

    def test_complete_build(self) -> None:
        provenance = Provenance(
            planning_run_id="run-1",
            pipeline_version="1.2.0",
            decision_trace=[
                DecisionRecord(
                    decision_id="decision-1",
                    decision_category=DecisionCategory.RESOURCE,
                    summary="Committed official repository posture.",
                )
            ],
        )
        strategy = ExecutionStrategyBuilder.build(
            _complete_risk_result(),
            strategy_id="strategy-complete",
            input_references=_input_references(),
            created_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
            summary="Degraded official repository plan.",
            invocation_reason=PlanningInvocationReason.DISCOVERY_PARTIAL,
            provenance=provenance,
        )
        self.assertEqual(strategy.metadata.status, PlanningStatus.DEGRADED)
        self.assertEqual(strategy.metadata.blocking_risk_count, 0)
        self.assertEqual(len(strategy.risk_assessment.degraded_risks), 1)
        self.assertTrue(strategy.adaptation_plan.adaptation_required)
        self.assertTrue(strategy.generation_plan.generation_required)
        self.assertEqual(strategy.provenance.planning_run_id, "run-1")
        self.assertEqual(len(strategy.provenance.decision_trace), 1)

    def test_empty_optional_modules(self) -> None:
        risk_result = RiskAssessmentResult(
            strategy=_strategy_snapshot(),
            resource_bindings=ResourceBindingSnapshot(),
            reuse_plan=ReusePlanSnapshot(),
            adaptation_plan=AdaptationPlanSnapshot(),
            generation_plan=GenerationPlanSnapshot(),
            risk_assessment=RiskAssessmentSnapshot(
                artifact_status_hint=PlanningStatus.PARTIAL,
            ),
        )
        strategy = ExecutionStrategyBuilder.build(
            risk_result,
            strategy_id="strategy-empty-modules",
            input_references=_input_references(),
            created_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
            summary="Partial plan with empty optional modules.",
        )
        self.assertEqual(strategy.resource_bindings.bindings, [])
        self.assertEqual(strategy.reuse_plan.components_to_reuse, [])
        self.assertEqual(strategy.generation_plan.modules_to_generate, [])
        self.assertEqual(strategy.risk_assessment.blocking_risks, [])

    def test_frozen_output_immutability(self) -> None:
        strategy = ExecutionStrategyBuilder.build(
            _minimal_risk_result(),
            strategy_id="strategy-frozen",
            input_references=_input_references(),
            created_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        )
        with self.assertRaises(Exception):
            strategy.metadata.summary = "changed"  # type: ignore[misc]

    def test_idempotent_build(self) -> None:
        risk_result = _minimal_risk_result()
        kwargs = {
            "strategy_id": "strategy-idempotent",
            "input_references": _input_references(),
            "created_at": datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
            "summary": "Idempotent build.",
        }
        first = ExecutionStrategyBuilder.build(risk_result, **kwargs)
        second = ExecutionStrategyBuilder.build(risk_result, **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first.model_dump(), second.model_dump())

    def test_validation_failure_propagation(self) -> None:
        risk_result = _minimal_risk_result(
            strategy=_strategy_snapshot(rationale=""),
        )
        with self.assertRaises(ExecutionStrategyValidationError):
            ExecutionStrategyBuilder.build(
                risk_result,
                strategy_id="strategy-invalid",
                input_references=_input_references(),
                created_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
            )

    def test_json_serialization_round_trip(self) -> None:
        strategy = ExecutionStrategyBuilder.build(
            _complete_risk_result(),
            strategy_id="strategy-json",
            input_references=_input_references(),
            created_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
            summary="JSON round-trip.",
        )
        restored = type(strategy).model_validate(json.loads(strategy.model_dump_json()))
        self.assertEqual(restored, strategy)

    def test_builder_preserves_runtime_values(self) -> None:
        risk_result = _complete_risk_result()
        strategy = ExecutionStrategyBuilder.build(
            risk_result,
            strategy_id="strategy-preserve",
            input_references=_input_references(),
            created_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
            summary="Preserve runtime values.",
        )
        self.assertEqual(strategy.strategy.rationale, risk_result.strategy.rationale)
        self.assertEqual(
            strategy.resource_bindings.combination_rationale,
            risk_result.resource_bindings.combination_rationale,
        )
        self.assertEqual(strategy.reuse_plan.reuse_mode, risk_result.reuse_plan.reuse_mode)
        self.assertEqual(
            strategy.generation_plan.generation_rationale,
            risk_result.generation_plan.generation_rationale,
        )
        self.assertEqual(
            strategy.risk_assessment.degraded_risks[0].risk_id,
            risk_result.risk_assessment.degraded_risks[0].risk_id,
        )
        self.assertNotIn(
            "selection_alignment_summary",
            strategy.resource_bindings.model_dump(),
        )
        self.assertNotIn(
            "artifact_status_hint",
            strategy.strategy.model_dump(),
        )
        self.assertNotIn(
            "artifact_status_hint",
            strategy.risk_assessment.model_dump(),
        )

    def test_builder_never_mutates_runtime_inputs(self) -> None:
        risk_result = _complete_risk_result()
        before = risk_result.model_dump()
        before_deep = copy.deepcopy(risk_result)
        ExecutionStrategyBuilder.build(
            risk_result,
            strategy_id="strategy-no-mutation",
            input_references=_input_references(),
            created_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        )
        self.assertEqual(risk_result.model_dump(), before)
        self.assertEqual(risk_result, before_deep)

    def test_metadata_status_maps_from_artifact_status_hint(self) -> None:
        risk_result = _minimal_risk_result(
            risk_assessment=RiskAssessmentSnapshot(artifact_status_hint=PlanningStatus.MANUAL_REVIEW),
        )
        strategy = ExecutionStrategyBuilder.build(
            risk_result,
            strategy_id="strategy-status-map",
            input_references=_input_references(),
            created_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        )
        self.assertEqual(strategy.metadata.status, PlanningStatus.MANUAL_REVIEW)

    def test_cumulative_runtime_chain_builds(self) -> None:
        strategy_stage = StrategyDecisionResult(strategy=_strategy_snapshot())
        binding_stage = ResourceBindingResult(
            strategy=strategy_stage.strategy,
            resource_bindings=_binding_snapshot(),
        )
        reuse_stage = ReusePlanResult(
            strategy=binding_stage.strategy,
            resource_bindings=binding_stage.resource_bindings,
            reuse_plan=ReusePlanSnapshot(reuse_mode=ReuseMode.AS_IS),
        )
        adaptation_stage = AdaptationPlanResult(
            strategy=reuse_stage.strategy,
            resource_bindings=reuse_stage.resource_bindings,
            reuse_plan=reuse_stage.reuse_plan,
            adaptation_plan=AdaptationPlanSnapshot(),
        )
        generation_stage = GenerationPlanResult(
            strategy=adaptation_stage.strategy,
            resource_bindings=adaptation_stage.resource_bindings,
            reuse_plan=adaptation_stage.reuse_plan,
            adaptation_plan=adaptation_stage.adaptation_plan,
            generation_plan=GenerationPlanSnapshot(),
        )
        risk_result = RiskAssessmentResult(
            strategy=generation_stage.strategy,
            resource_bindings=generation_stage.resource_bindings,
            reuse_plan=generation_stage.reuse_plan,
            adaptation_plan=generation_stage.adaptation_plan,
            generation_plan=generation_stage.generation_plan,
            risk_assessment=RiskAssessmentSnapshot(artifact_status_hint=PlanningStatus.COMPLETE),
        )
        strategy = ExecutionStrategyBuilder.build(
            risk_result,
            strategy_id="strategy-chain",
            input_references=_input_references(),
            created_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
            summary="Built from cumulative chain.",
        )
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)
        self.assertEqual(strategy.reuse_plan.reuse_mode, ReuseMode.AS_IS)


if __name__ == "__main__":
    unittest.main()
