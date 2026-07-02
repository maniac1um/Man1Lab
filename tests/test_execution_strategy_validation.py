import unittest
from datetime import UTC, datetime

from models.execution_strategy import (
    SCHEMA_VERSION,
    PlanningStatus,
    StrategyPosture,
)
from validation.exceptions import ExecutionStrategyValidationError
from validation.execution_strategy import (
    build_execution_strategy,
    normalize_execution_strategy,
    validate_execution_strategy,
)


def _minimal_payload(**overrides) -> dict:
    payload = {
        "metadata": {
            "strategy_id": "strategy-1",
            "created_at": "2026-07-03T12:00:00+00:00",
            "status": "complete",
            "summary": "Official repo reuse.",
            "binding_count": 1,
            "blocking_risk_count": 0,
        },
        "input_references": {
            "analysis_reference": {
                "analysis_schema_version": "1.0",
                "paper_title": "Test Paper",
                "analysis_content_hash": "analysis-hash",
            },
            "discovery_reference": {
                "discovery_schema_version": "1.0",
                "discovery_id": "disc-1",
                "discovery_content_hash": "discovery-hash",
                "discovery_status": "complete",
            },
        },
        "strategy": {
            "primary_posture": "official_repository",
            "scope_commitment": "full_reproduction",
            "rationale": "Use official repository selected by Discovery.",
            "confidence": 0.9,
        },
        "resource_bindings": {
            "bindings": [
                {
                    "binding_id": "binding-repo",
                    "candidate_id": "candidate-repo",
                    "role": "primary_repository",
                    "usage_intent": "execute_directly",
                }
            ],
            "anchor_binding_id": "binding-repo",
        },
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(payload.get(key), dict):
            merged = dict(payload[key])
            merged.update(value)
            payload[key] = merged
        else:
            payload[key] = value
    return payload


class ExecutionStrategyValidationTest(unittest.TestCase):
    def test_build_minimal_strategy(self) -> None:
        strategy = build_execution_strategy(_minimal_payload())
        self.assertEqual(strategy.schema_version, SCHEMA_VERSION)
        self.assertEqual(strategy.metadata.status, PlanningStatus.COMPLETE)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)
        self.assertEqual(len(strategy.resource_bindings.bindings), 1)

    def test_normalize_injects_schema_version_default(self) -> None:
        normalized = normalize_execution_strategy(_minimal_payload())
        self.assertEqual(normalized["schema_version"], SCHEMA_VERSION)

    def test_normalize_empty_optional_modules(self) -> None:
        normalized = normalize_execution_strategy(_minimal_payload())
        self.assertEqual(normalized["reuse_plan"]["components_to_reuse"], [])
        self.assertEqual(normalized["generation_plan"]["modules_to_generate"], [])
        self.assertEqual(normalized["risk_assessment"]["blocking_risks"], [])
        self.assertEqual(normalized["provenance"]["decision_trace"], [])

    def test_normalize_enum_strings(self) -> None:
        normalized = normalize_execution_strategy(
            _minimal_payload(
                metadata={"status": "degraded", "strategy_posture": "hybrid"},
                strategy={
                    "primary_posture": "community_fork",
                    "scope_commitment": "narrowed_scope",
                    "scope_narrowing_rationale": "Checkpoint unavailable.",
                    "rationale": "Use community fork.",
                },
            )
        )
        self.assertEqual(normalized["metadata"]["status"], PlanningStatus.DEGRADED)
        self.assertEqual(normalized["strategy"]["primary_posture"], StrategyPosture.COMMUNITY_FORK)

    def test_validate_rejects_missing_metadata(self) -> None:
        payload = _minimal_payload()
        del payload["metadata"]
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_missing_analysis_hash(self) -> None:
        payload = _minimal_payload()
        del payload["input_references"]["analysis_reference"]["analysis_content_hash"]
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_missing_discovery_hash(self) -> None:
        payload = _minimal_payload()
        del payload["input_references"]["discovery_reference"]["discovery_content_hash"]
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_empty_strategy_rationale(self) -> None:
        payload = _minimal_payload()
        payload["strategy"]["rationale"] = "   "
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_duplicate_binding_ids(self) -> None:
        payload = _minimal_payload(
            resource_bindings={
                "bindings": [
                    {
                        "binding_id": "binding-repo",
                        "candidate_id": "candidate-a",
                        "role": "primary_repository",
                    },
                    {
                        "binding_id": "binding-repo",
                        "candidate_id": "candidate-b",
                        "role": "fallback_repository",
                    },
                ]
            }
        )
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_duplicate_candidate_ids_in_bindings(self) -> None:
        payload = _minimal_payload(
            resource_bindings={
                "bindings": [
                    {
                        "binding_id": "binding-a",
                        "candidate_id": "candidate-same",
                        "role": "primary_repository",
                    },
                    {
                        "binding_id": "binding-b",
                        "candidate_id": "candidate-same",
                        "role": "checkpoint",
                    },
                ]
            }
        )
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_unknown_anchor_binding(self) -> None:
        payload = _minimal_payload(
            resource_bindings={
                "bindings": [
                    {
                        "binding_id": "binding-repo",
                        "candidate_id": "candidate-repo",
                        "role": "primary_repository",
                    }
                ],
                "anchor_binding_id": "missing-binding",
            }
        )
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_override_without_rationale(self) -> None:
        payload = _minimal_payload(
            resource_bindings={
                "bindings": [
                    {
                        "binding_id": "binding-repo",
                        "candidate_id": "candidate-repo",
                        "role": "primary_repository",
                        "overrides_discovery_selection": True,
                    }
                ],
                "anchor_binding_id": "binding-repo",
            }
        )
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_narrowed_scope_without_rationale(self) -> None:
        payload = _minimal_payload(
            strategy={
                "primary_posture": "official_repository",
                "scope_commitment": "narrowed_scope",
                "rationale": "Narrow reproduction scope.",
            }
        )
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_duplicate_risk_ids(self) -> None:
        payload = _minimal_payload(
            risk_assessment={
                "blocking_risks": [
                    {
                        "risk_id": "risk-1",
                        "severity": "blocking",
                        "category": "license",
                    },
                    {
                        "risk_id": "risk-1",
                        "severity": "degraded",
                        "category": "other",
                    },
                ]
            }
        )
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_duplicate_generation_targets(self) -> None:
        payload = _minimal_payload(
            generation_plan={
                "generation_required": True,
                "generation_scope": "missing_modules",
                "modules_to_generate": [
                    {
                        "analysis_module": "method",
                        "generation_intent": "implement_from_paper",
                        "priority": "blocking",
                    },
                    {
                        "analysis_module": "method",
                        "generation_intent": "stub_for_integration",
                        "priority": "optional",
                    },
                ],
            }
        )
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_metadata_binding_count_mismatch(self) -> None:
        payload = _minimal_payload(metadata={"binding_count": 2})
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_validate_rejects_invalid_enum_value(self) -> None:
        payload = _minimal_payload()
        payload["strategy"]["primary_posture"] = "not_a_posture"
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(payload)

    def test_build_round_trip_serialization(self) -> None:
        strategy = build_execution_strategy(_minimal_payload())
        restored = build_execution_strategy(strategy.model_dump(mode="json"))
        self.assertEqual(restored.metadata.strategy_id, "strategy-1")
        self.assertEqual(restored.resource_bindings.anchor_binding_id, "binding-repo")

    def test_normalize_then_validate_cross_reference_reuse_component(self) -> None:
        payload = _minimal_payload(
            reuse_plan={
                "reuse_mode": "as_is",
                "components_to_reuse": [
                    {
                        "binding_id": "missing-binding",
                        "component_label": "training_code",
                    }
                ],
            }
        )
        normalized = normalize_execution_strategy(payload)
        with self.assertRaises(ExecutionStrategyValidationError):
            validate_execution_strategy(normalized)

    def test_provenance_decision_trace_normalization(self) -> None:
        now = datetime.now(UTC).isoformat()
        normalized = normalize_execution_strategy(
            _minimal_payload(
                provenance={
                    "planning_run_id": "run-1",
                    "decision_trace": [
                        {
                            "decision_id": "decision-1",
                            "decision_category": "resource",
                            "summary": "Bound repository.",
                            "timestamp": now,
                        }
                    ],
                }
            )
        )
        strategy = build_execution_strategy(normalized)
        self.assertEqual(len(strategy.provenance.decision_trace), 1)
        self.assertEqual(strategy.provenance.decision_trace[0].decision_id, "decision-1")


if __name__ == "__main__":
    unittest.main()
