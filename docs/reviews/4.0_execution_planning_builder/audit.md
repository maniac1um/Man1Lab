# ExecutionStrategyBuilder Audit — Phase 4

**Date:** 2026-06-29  
**Scope:** `execution_planning/builder.py` canonical assembly layer  
**Verdict:** **Ready for ExecutionPlanningWorkflow Skeleton**

---

## Files Added

| File | Purpose |
|------|---------|
| `execution_planning/__init__.py` | Package export for `ExecutionStrategyBuilder` |
| `execution_planning/builder.py` | Deterministic assembly from `RiskAssessmentResult` to `ExecutionStrategy` |
| `tests/test_execution_strategy_builder.py` | Builder tests (11 tests) |
| `docs/reviews/execution_planning_builder_phase_4/audit.md` | This audit |

## Files Modified

None.

---

## Builder Responsibilities

| Responsibility | Implementation |
|----------------|----------------|
| Consume final cumulative runtime result | `build(risk_result: RiskAssessmentResult, ...)` |
| Map stage snapshots to canonical modules | `_map_*_snapshot` helpers |
| Assemble `metadata` | Identity/timing from workflow envelope; denormalized counts from runtime |
| Pass through `input_references` | Unmodified from workflow-supplied `InputReferences` |
| Pass through `provenance` | Unmodified from workflow-supplied `Provenance` |
| Inject `schema_version` | `SCHEMA_VERSION` constant |
| Delegate validation | `normalize_execution_strategy` → `validate_execution_strategy` → `build_execution_strategy` |

The builder does **not** perform engineering reasoning, validation logic itself, or workflow orchestration.

---

## Assembly Mapping

| Runtime source | Canonical module | Mapping rule |
|----------------|------------------|--------------|
| `risk_result.strategy` | `strategy` | Copy all fields except `artifact_status_hint` |
| `risk_result.resource_bindings` | `resource_bindings` | Copy all fields except `selection_alignment_summary` |
| `risk_result.reuse_plan` | `reuse_plan` | Direct copy |
| `risk_result.adaptation_plan` | `adaptation_plan` | Direct copy |
| `risk_result.generation_plan` | `generation_plan` | Direct copy |
| `risk_result.risk_assessment` | `risk_assessment` | Copy all fields except `artifact_status_hint` |
| `risk_result.risk_assessment.artifact_status_hint` | `metadata.status` | Deterministic denormalization |
| `risk_result.strategy.primary_posture` | `metadata.strategy_posture` | Deterministic denormalization |
| `len(resource_bindings.bindings)` | `metadata.binding_count` | Count only — no reorder |
| `len(blocking_risks)` | `metadata.blocking_risk_count` | Count only — no reorder |
| Posture / manual actions | `metadata.manual_action_required` | Deterministic denormalization |
| Workflow `strategy_id`, `created_at`, `summary`, etc. | `metadata` | Injected envelope fields |
| Workflow `input_references` | `input_references` | Pass-through |
| Workflow `provenance` | `provenance` | Pass-through |
| — | `schema_version` | Injected constant |

Runtime-only fields (`artifact_status_hint`, `selection_alignment_summary`) are excluded from canonical modules.

---

## Validation Flow

```text
RiskAssessmentResult
        ↓
_assemble_candidate()          # deterministic dict assembly
        ↓
normalize_execution_strategy()
        ↓
validate_execution_strategy()
        ↓
build_execution_strategy()
        ↓
ExecutionStrategy
```

Validation remains owned by `validation/execution_strategy.py`. The builder never implements structural rules itself.

---

## Builder Invariants

| Invariant | Status |
|-----------|--------|
| No engineering decision changes | Yes — snapshots copied verbatim |
| No new runtime information created | Yes — only schema version and metadata envelope injection |
| Stage outputs preserved exactly | Yes — tested |
| Deterministic | Yes — same inputs produce same artifact |
| Idempotent | Yes — tested |
| Side-effect free | Yes — runtime inputs not mutated (tested) |

---

## Architecture Boundary

| Constraint | Status |
|------------|--------|
| Depends only on `models.execution_strategy` | Yes |
| Depends only on `models.execution_planning_runtime` | Yes |
| Depends only on `validation.execution_strategy` | Yes |
| No planner imports | Yes |
| No workflow imports | Yes |
| No providers / services | Yes |
| No Hydra / MLflow / GitHub / OpenAlex / HuggingFace | Yes |

---

## Relationship to Runtime Models

- **Input contract:** `RiskAssessmentResult` — the final cumulative stage result containing all six snapshot modules.
- **Never consumes** individual stage snapshots in isolation; workflow passes the full cumulative result.
- **Excludes** runtime-only diagnostic fields from canonical output.
- Workflow supplies assembly envelope (`strategy_id`, `input_references`, `provenance`, optional `created_at` / `summary`) — these are not engineering decisions and are prepared by the coordinator before assembly.

---

## Relationship to ExecutionStrategy

- `ExecutionStrategyBuilder` is the **only** assembly point converting runtime planning state into the canonical artifact.
- Output is a validated, frozen `ExecutionStrategy` ready for downstream Planner consumption.
- Only `ExecutionStrategy` leaves the Execution Planning capability boundary.

---

## Test Coverage

```text
pixi run test tests/test_execution_strategy_builder.py
273 passed in 10.38s
```

New tests (`tests/test_execution_strategy_builder.py`): **11**

| Test | Coverage |
|------|----------|
| `test_minimal_build` | Minimal valid assembly |
| `test_complete_build` | All modules populated + provenance pass-through |
| `test_empty_optional_modules` | Empty bindings/plans/risks |
| `test_frozen_output_immutability` | Frozen canonical output |
| `test_idempotent_build` | Same inputs → same artifact |
| `test_validation_failure_propagation` | `ExecutionStrategyValidationError` surfaces |
| `test_json_serialization_round_trip` | Canonical JSON round-trip |
| `test_builder_preserves_runtime_values` | Field-level preservation; runtime-only fields excluded |
| `test_builder_never_mutates_runtime_inputs` | Input immutability |
| `test_metadata_status_maps_from_artifact_status_hint` | Status denormalization mapping |
| `test_cumulative_runtime_chain_builds` | Stage chain → final result → build |

---

## Remaining Technical Debt

| Item | Phase |
|------|-------|
| `ExecutionPlanningWorkflow` skeleton | Next phase |
| Stage services and orchestration | Workflow phase |
| Cross-artifact validation against linked `ResearchResourceDiscovery` | Workflow validation stage |
| `decision_trace` assembly from all stage `decision_notes` | Workflow coordinator (before builder) |
| `metadata.strategy_id` / `created_at` generation | Workflow coordinator |
| Package re-export from top-level `__init__.py` | Optional cosmetic |

---

## Verdict

**Ready for ExecutionPlanningWorkflow Skeleton**

`ExecutionStrategyBuilder` is the single canonical assembly point for Execution Planning. Runtime stage results map deterministically to `ExecutionStrategy` through the existing validation layer, with no workflow, stage logic, orchestration, or engineering reasoning in scope for this phase.
