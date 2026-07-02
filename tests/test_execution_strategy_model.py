import copy
import json
import unittest
from datetime import UTC, datetime

from models.execution_strategy import (
    SCHEMA_VERSION,
    AdaptationPlan,
    AdaptationScope,
    AdaptationTrigger,
    AdaptationTriggerType,
    AnalysisModule,
    AnalysisReference,
    AuthorizationLevel,
    AuthorizedModification,
    BindingRole,
    DecisionCategory,
    DecisionRecord,
    DiscoveryReference,
    ExecutionStrategy,
    ExcludedComponent,
    FallbackStrategy,
    GenerationIntent,
    GenerationPlan,
    GenerationPriority,
    GenerationScope,
    GenerationTarget,
    InputReferences,
    ManualAction,
    ModificationClass,
    PlanningInvocationReason,
    PlanningStatus,
    Provenance,
    RejectedPosture,
    ResourceBinding,
    ResourceBindings,
    ReuseComponent,
    ReuseExtent,
    ReuseMode,
    ReusePlan,
    RiskAssessment,
    RiskCategory,
    RiskRecord,
    RiskSeverity,
    ScopeCommitment,
    Strategy,
    StrategyMetadata,
    StrategyPosture,
    UsageIntent,
)
from models.research_resource_discovery import DiscoveryStatus


def _sample_strategy() -> ExecutionStrategy:
    now = datetime.now(UTC)
    return ExecutionStrategy(
        metadata=StrategyMetadata(
            strategy_id="strategy-1",
            created_at=now,
            status=PlanningStatus.COMPLETE,
            summary="Official repo reuse with checkpoint gap accepted.",
            reproduction_scope="training",
            invocation_reason=PlanningInvocationReason.DISCOVERY_COMPLETE,
            strategy_posture=StrategyPosture.OFFICIAL_REPOSITORY,
            binding_count=1,
            blocking_risk_count=0,
            manual_action_required=False,
        ),
        input_references=InputReferences(
            analysis_reference=AnalysisReference(
                analysis_schema_version="1.0",
                paper_title="Deep Residual Learning for Image Recognition",
                arxiv_id="1512.03385",
                analysis_content_hash="analysis-hash",
                reproduction_scope="training",
                analysis_gap_categories=["repository"],
            ),
            discovery_reference=DiscoveryReference(
                discovery_schema_version="1.0",
                discovery_id="disc-1",
                discovery_content_hash="discovery-hash",
                discovery_status=DiscoveryStatus.COMPLETE,
                selection_ids_used=["selection-need-repo-0"],
                unresolved_discovery_gap_count=0,
            ),
        ),
        strategy=Strategy(
            primary_posture=StrategyPosture.OFFICIAL_REPOSITORY,
            scope_commitment=ScopeCommitment.FULL_REPRODUCTION,
            rationale="Use official repository selected by Discovery.",
            deciding_factors=["discovery_selection_official", "verification_pass"],
            confidence=0.9,
            alternative_postures_rejected=[
                RejectedPosture(
                    posture=StrategyPosture.GREENFIELD,
                    rejection_reason="Official repository verified.",
                )
            ],
        ),
        resource_bindings=ResourceBindings(
            bindings=[
                ResourceBinding(
                    binding_id="binding-repo",
                    candidate_id="candidate-repo",
                    selection_id="selection-need-repo-0",
                    resource_need_id="need-repository-0",
                    role=BindingRole.PRIMARY_REPOSITORY,
                    usage_intent=UsageIntent.EXECUTE_DIRECTLY,
                    binding_rationale="Primary official repository.",
                )
            ],
            anchor_binding_id="binding-repo",
            combination_rationale="Single official repository anchors reproduction.",
        ),
        reuse_plan=ReusePlan(
            reuse_mode=ReuseMode.AS_IS,
            primary_reuse_binding_id="binding-repo",
            components_to_reuse=[
                ReuseComponent(
                    binding_id="binding-repo",
                    component_label="training_code",
                    reuse_extent=ReuseExtent.FULL,
                )
            ],
            components_excluded=[
                ExcludedComponent(
                    candidate_id="candidate-fork",
                    exclusion_reason="Community fork not selected.",
                )
            ],
            reuse_assumptions=["Official train script matches paper method."],
        ),
        adaptation_plan=AdaptationPlan(
            adaptation_required=False,
            adaptation_scope=AdaptationScope.NONE,
            authorized_modifications=[
                AuthorizedModification(
                    modification_class=ModificationClass.DEPENDENCY_PIN,
                    authorization_level=AuthorizationLevel.PLANNER_TASK,
                )
            ],
            adaptation_triggers=[
                AdaptationTrigger(
                    trigger_type=AdaptationTriggerType.VERIFICATION_PARTIAL,
                    description="No adaptation required.",
                )
            ],
        ),
        generation_plan=GenerationPlan(
            generation_required=False,
            generation_scope=GenerationScope.NONE,
            modules_to_generate=[
                GenerationTarget(
                    analysis_module=AnalysisModule.METHOD,
                    generation_intent=GenerationIntent.IMPLEMENT_FROM_PAPER,
                    priority=GenerationPriority.OPTIONAL,
                )
            ],
            generation_rationale="Reuse official repository.",
        ),
        risk_assessment=RiskAssessment(
            overall_confidence=0.85,
            blocking_risks=[],
            degraded_risks=[
                RiskRecord(
                    risk_id="risk-1",
                    severity=RiskSeverity.DEGRADED,
                    category=RiskCategory.UNRESOLVED_RESOURCE,
                    description="Checkpoint not verified.",
                    mitigation="Proceed with training from scratch weights.",
                )
            ],
            fallback_strategies=[
                FallbackStrategy(
                    fallback_order=1,
                    posture=StrategyPosture.COMMUNITY_FORK,
                    trigger_condition="Primary repository clone fails.",
                    fallback_binding_ids=["binding-fallback"],
                )
            ],
            manual_actions_required=[
                ManualAction(
                    action_id="manual-1",
                    description="Confirm dataset license.",
                    blocks_planner=False,
                )
            ],
            abort_conditions=["License blocked by policy."],
        ),
        provenance=Provenance(
            planning_run_id="plan-run-1",
            pipeline_version="1.2.0",
            stage_timestamps={"strategy_decision": now},
            degradation_notes=[],
            configuration_fingerprint="cfg-fingerprint",
            decision_trace=[
                DecisionRecord(
                    decision_id="decision-1",
                    decision_category=DecisionCategory.RESOURCE,
                    summary="Bound official repository.",
                    inputs_consulted=["discovery.selections[0]"],
                    timestamp=now,
                )
            ],
        ),
    )


class ExecutionStrategyModelTest(unittest.TestCase):
    def test_schema_version_constant(self) -> None:
        strategy = _sample_strategy()
        self.assertEqual(strategy.schema_version, SCHEMA_VERSION)

    def test_construction_with_nested_models(self) -> None:
        strategy = _sample_strategy()
        self.assertEqual(strategy.metadata.strategy_id, "strategy-1")
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)
        self.assertEqual(len(strategy.resource_bindings.bindings), 1)
        self.assertEqual(strategy.resource_bindings.bindings[0].role, BindingRole.PRIMARY_REPOSITORY)
        self.assertEqual(strategy.reuse_plan.reuse_mode, ReuseMode.AS_IS)
        self.assertEqual(strategy.adaptation_plan.adaptation_scope, AdaptationScope.NONE)
        self.assertEqual(strategy.generation_plan.generation_scope, GenerationScope.NONE)
        self.assertEqual(len(strategy.risk_assessment.degraded_risks), 1)
        self.assertEqual(len(strategy.provenance.decision_trace), 1)

    def test_default_values_for_optional_modules(self) -> None:
        now = datetime.now(UTC)
        minimal = ExecutionStrategy(
            metadata=StrategyMetadata(
                strategy_id="strategy-min",
                created_at=now,
                status=PlanningStatus.PARTIAL,
            ),
            input_references=InputReferences(
                analysis_reference=AnalysisReference(
                    analysis_schema_version="1.0",
                    paper_title="Minimal Paper",
                    analysis_content_hash="hash",
                ),
                discovery_reference=DiscoveryReference(
                    discovery_schema_version="1.0",
                    discovery_id="disc-min",
                    discovery_content_hash="disc-hash",
                    discovery_status=DiscoveryStatus.SKIPPED,
                ),
            ),
            strategy=Strategy(
                primary_posture=StrategyPosture.GREENFIELD,
                rationale="No discovery input.",
            ),
        )
        self.assertEqual(minimal.resource_bindings.bindings, [])
        self.assertEqual(minimal.reuse_plan.components_to_reuse, [])
        self.assertEqual(minimal.adaptation_plan.authorized_modifications, [])
        self.assertEqual(minimal.generation_plan.modules_to_generate, [])
        self.assertEqual(minimal.risk_assessment.blocking_risks, [])
        self.assertEqual(minimal.provenance.decision_trace, [])
        self.assertEqual(minimal.metadata.summary, "")
        self.assertEqual(minimal.metadata.binding_count, 0)

    def test_enum_parsing_from_strings(self) -> None:
        now = datetime.now(UTC)
        strategy = ExecutionStrategy.model_validate(
            {
                "metadata": {
                    "strategy_id": "strategy-enum",
                    "created_at": now.isoformat(),
                    "status": "degraded",
                    "strategy_posture": "hybrid",
                },
                "input_references": {
                    "analysis_reference": {
                        "analysis_schema_version": "1.0",
                        "paper_title": "Enum Paper",
                        "analysis_content_hash": "hash",
                    },
                    "discovery_reference": {
                        "discovery_schema_version": "1.0",
                        "discovery_id": "disc-enum",
                        "discovery_content_hash": "disc-hash",
                        "discovery_status": "partial",
                    },
                },
                "strategy": {
                    "primary_posture": "community_fork",
                    "scope_commitment": "narrowed_scope",
                },
                "resource_bindings": {
                    "bindings": [
                        {
                            "binding_id": "b1",
                            "candidate_id": "c1",
                            "role": "checkpoint",
                            "usage_intent": "reference_only",
                        }
                    ]
                },
                "reuse_plan": {"reuse_mode": "fork_based"},
                "adaptation_plan": {"adaptation_scope": "moderate"},
                "generation_plan": {"generation_scope": "missing_modules"},
                "risk_assessment": {
                    "blocking_risks": [
                        {
                            "risk_id": "r1",
                            "severity": "blocking",
                            "category": "license",
                        }
                    ]
                },
            }
        )
        self.assertEqual(strategy.metadata.status, PlanningStatus.DEGRADED)
        self.assertEqual(strategy.metadata.strategy_posture, StrategyPosture.HYBRID)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.COMMUNITY_FORK)
        self.assertEqual(strategy.strategy.scope_commitment, ScopeCommitment.NARROWED_SCOPE)
        self.assertEqual(
            strategy.input_references.discovery_reference.discovery_status,
            DiscoveryStatus.PARTIAL,
        )
        self.assertEqual(strategy.resource_bindings.bindings[0].role, BindingRole.CHECKPOINT)
        self.assertEqual(
            strategy.resource_bindings.bindings[0].usage_intent,
            UsageIntent.REFERENCE_ONLY,
        )
        self.assertEqual(strategy.reuse_plan.reuse_mode, ReuseMode.FORK_BASED)
        self.assertEqual(strategy.adaptation_plan.adaptation_scope, AdaptationScope.MODERATE)
        self.assertEqual(strategy.generation_plan.generation_scope, GenerationScope.MISSING_MODULES)
        self.assertEqual(strategy.risk_assessment.blocking_risks[0].severity, RiskSeverity.BLOCKING)
        self.assertEqual(strategy.risk_assessment.blocking_risks[0].category, RiskCategory.LICENSE)

    def test_serialization_round_trip(self) -> None:
        strategy = _sample_strategy()
        payload = strategy.model_dump(mode="json")
        restored = ExecutionStrategy.model_validate(payload)
        self.assertEqual(restored, strategy)

    def test_json_serialization(self) -> None:
        strategy = _sample_strategy()
        encoded = strategy.model_dump_json()
        decoded = json.loads(encoded)
        restored = ExecutionStrategy.model_validate(decoded)
        self.assertEqual(restored.metadata.strategy_id, "strategy-1")
        self.assertEqual(
            restored.input_references.analysis_reference.paper_title,
            "Deep Residual Learning for Image Recognition",
        )

    def test_frozen_model(self) -> None:
        strategy = _sample_strategy()
        with self.assertRaises(Exception):
            strategy.metadata = strategy.metadata  # type: ignore[misc]

    def test_deep_copy_via_model_copy(self) -> None:
        strategy = _sample_strategy()
        copied = strategy.model_copy(deep=True)
        self.assertEqual(copied, strategy)
        self.assertIsNot(copied.resource_bindings, strategy.resource_bindings)
        self.assertIsNot(copied.risk_assessment, strategy.risk_assessment)

    def test_deep_copy_via_copy_module(self) -> None:
        strategy = _sample_strategy()
        copied = copy.deepcopy(strategy)
        self.assertEqual(copied, strategy)
        self.assertIsNot(copied.provenance, strategy.provenance)

    def test_input_references_nested_structure(self) -> None:
        strategy = _sample_strategy()
        self.assertEqual(
            strategy.input_references.analysis_reference.analysis_gap_categories,
            ["repository"],
        )
        self.assertEqual(
            strategy.input_references.discovery_reference.selection_ids_used,
            ["selection-need-repo-0"],
        )

    def test_generation_target_enums(self) -> None:
        target = GenerationTarget(
            analysis_module=AnalysisModule.EVALUATION,
            generation_intent=GenerationIntent.STUB_FOR_INTEGRATION,
            priority=GenerationPriority.DEGRADED,
        )
        self.assertEqual(target.analysis_module, AnalysisModule.EVALUATION)
        self.assertEqual(target.generation_intent, GenerationIntent.STUB_FOR_INTEGRATION)
        self.assertEqual(target.priority, GenerationPriority.DEGRADED)


if __name__ == "__main__":
    unittest.main()
