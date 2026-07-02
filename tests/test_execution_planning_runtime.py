import json
import unittest
from datetime import UTC, datetime

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
    AnalysisModule,
    BindingRole,
    GenerationIntent,
    GenerationPriority,
    GenerationScope,
    PlanningStatus,
    ResourceBinding,
    ReuseMode,
    RiskCategory,
    RiskRecord,
    RiskSeverity,
    ScopeCommitment,
    StrategyPosture,
    UsageIntent,
)


def _strategy_snapshot() -> StrategyDecisionSnapshot:
    return StrategyDecisionSnapshot(
        primary_posture=StrategyPosture.OFFICIAL_REPOSITORY,
        scope_commitment=ScopeCommitment.FULL_REPRODUCTION,
        rationale="Use official repository.",
        deciding_factors=["verification_pass"],
        confidence=0.9,
        artifact_status_hint=PlanningStatus.COMPLETE,
    )


def _binding_snapshot() -> ResourceBindingSnapshot:
    return ResourceBindingSnapshot(
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
    )


class ExecutionPlanningRuntimeModelTest(unittest.TestCase):
    def test_stage_runtime_metadata_defaults(self) -> None:
        result = StrategyDecisionResult(strategy=_strategy_snapshot())
        self.assertEqual(result.stage_name, "strategy_decision")
        self.assertEqual(result.stage_status, StageRuntimeStatus.SUCCESS)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.diagnostics, {})
        self.assertIsNone(result.started_at)
        self.assertIsNone(result.completed_at)
        self.assertEqual(result.decision_notes, "")

    def test_snapshot_defaults(self) -> None:
        binding = ResourceBindingSnapshot()
        reuse = ReusePlanSnapshot()
        risk = RiskAssessmentSnapshot()
        self.assertEqual(binding.bindings, [])
        self.assertEqual(reuse.reuse_mode, ReuseMode.NOT_APPLICABLE)
        self.assertEqual(risk.overall_confidence, 0.0)
        self.assertEqual(risk.artifact_status_hint, PlanningStatus.PARTIAL)

    def test_resource_binding_result_construction(self) -> None:
        now = datetime.now(UTC)
        result = ResourceBindingResult(
            started_at=now,
            completed_at=now,
            stage_status=StageRuntimeStatus.PARTIAL,
            decision_notes="Bound official repository.",
            warnings=["No checkpoint selection available."],
            strategy=_strategy_snapshot(),
            resource_bindings=_binding_snapshot(),
        )
        self.assertEqual(result.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)
        self.assertEqual(len(result.resource_bindings.bindings), 1)
        self.assertEqual(result.resource_bindings.anchor_binding_id, "binding-repo")

    def test_cumulative_reuse_plan_result(self) -> None:
        result = ReusePlanResult(
            strategy=_strategy_snapshot(),
            resource_bindings=_binding_snapshot(),
            reuse_plan=ReusePlanSnapshot(
                reuse_mode=ReuseMode.AS_IS,
                primary_reuse_binding_id="binding-repo",
            ),
        )
        self.assertEqual(result.reuse_plan.reuse_mode, ReuseMode.AS_IS)
        self.assertEqual(result.resource_bindings.bindings[0].binding_id, "binding-repo")

    def test_cumulative_adaptation_plan_result(self) -> None:
        result = AdaptationPlanResult(
            strategy=_strategy_snapshot(),
            resource_bindings=_binding_snapshot(),
            reuse_plan=ReusePlanSnapshot(reuse_mode=ReuseMode.AS_IS),
            adaptation_plan=AdaptationPlanSnapshot(adaptation_required=False),
        )
        self.assertFalse(result.adaptation_plan.adaptation_required)
        self.assertEqual(result.strategy.rationale, "Use official repository.")

    def test_cumulative_generation_plan_result(self) -> None:
        result = GenerationPlanResult(
            strategy=_strategy_snapshot(),
            resource_bindings=_binding_snapshot(),
            reuse_plan=ReusePlanSnapshot(reuse_mode=ReuseMode.AS_IS),
            adaptation_plan=AdaptationPlanSnapshot(),
            generation_plan=GenerationPlanSnapshot(
                generation_required=False,
                generation_scope=GenerationScope.NONE,
            ),
        )
        self.assertEqual(result.generation_plan.generation_scope, GenerationScope.NONE)

    def test_risk_assessment_result_full_chain(self) -> None:
        result = RiskAssessmentResult(
            stage_status=StageRuntimeStatus.DEGRADED,
            errors=["Recovered from partial discovery input."],
            diagnostics={"discovery_status": "partial"},
            strategy=_strategy_snapshot(),
            resource_bindings=_binding_snapshot(),
            reuse_plan=ReusePlanSnapshot(reuse_mode=ReuseMode.AS_IS),
            adaptation_plan=AdaptationPlanSnapshot(),
            generation_plan=GenerationPlanSnapshot(),
            risk_assessment=RiskAssessmentSnapshot(
                overall_confidence=0.7,
                degraded_risks=[
                    RiskRecord(
                        risk_id="risk-1",
                        severity=RiskSeverity.DEGRADED,
                        category=RiskCategory.UNRESOLVED_RESOURCE,
                        description="Checkpoint unresolved.",
                    )
                ],
                artifact_status_hint=PlanningStatus.DEGRADED,
            ),
        )
        self.assertEqual(result.stage_status, StageRuntimeStatus.DEGRADED)
        self.assertEqual(len(result.risk_assessment.degraded_risks), 1)
        self.assertEqual(result.risk_assessment.artifact_status_hint, PlanningStatus.DEGRADED)

    def test_frozen_runtime_models(self) -> None:
        result = StrategyDecisionResult(strategy=_strategy_snapshot())
        with self.assertRaises(Exception):
            result.stage_status = StageRuntimeStatus.PARTIAL  # type: ignore[misc]

    def test_json_round_trip_strategy_decision(self) -> None:
        result = StrategyDecisionResult(
            strategy=_strategy_snapshot(),
            warnings=["discovery partial"],
        )
        restored = StrategyDecisionResult.model_validate(json.loads(result.model_dump_json()))
        self.assertEqual(restored, result)

    def test_json_round_trip_risk_assessment(self) -> None:
        result = RiskAssessmentResult(
            strategy=_strategy_snapshot(),
            resource_bindings=_binding_snapshot(),
            generation_plan=GenerationPlanSnapshot(
                modules_to_generate=[
                    {
                        "analysis_module": AnalysisModule.METHOD.value,
                        "generation_intent": GenerationIntent.IMPLEMENT_FROM_PAPER.value,
                        "priority": GenerationPriority.BLOCKING.value,
                    }
                ]
            ),
            risk_assessment=RiskAssessmentSnapshot(overall_confidence=0.8),
        )
        payload = json.loads(result.model_dump_json())
        restored = RiskAssessmentResult.model_validate(payload)
        self.assertEqual(
            restored.generation_plan.modules_to_generate[0].analysis_module,
            AnalysisModule.METHOD,
        )
        self.assertEqual(restored.risk_assessment.overall_confidence, 0.8)

    def test_nested_snapshot_serialization(self) -> None:
        result = GenerationPlanResult(
            strategy=_strategy_snapshot(),
            resource_bindings=_binding_snapshot(),
            reuse_plan=ReusePlanSnapshot(),
            adaptation_plan=AdaptationPlanSnapshot(),
            generation_plan=GenerationPlanSnapshot(generation_required=True),
        )
        payload = result.model_dump(mode="json")
        self.assertEqual(payload["stage_name"], "generation_planning")
        self.assertTrue(payload["generation_plan"]["generation_required"])
        self.assertEqual(payload["strategy"]["primary_posture"], "official_repository")


if __name__ == "__main__":
    unittest.main()
