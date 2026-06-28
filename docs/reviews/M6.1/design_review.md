# Design Review Report — M6.1 Reproduction Verification

**Milestone:** M6.1 — Reproduction Verification  
**Capability:** Reviewer / Verification  
**Status:** Complete  
**Tests:** Skipped in this session (test module added, not executed)

---

# 1. Verification Pipeline

Complete verification path after execution:

```text
Workspace
        ×
ExecutionResult
        ↓
WorkflowOrchestrator._run_stage(PipelineStage.REVIEWER, ...)
        ↓
Reviewer.run(workspace, execution_result)
        ↓
VerificationService.verify(workspace, execution_result)
        ↓
VerificationResult
        ↓
history.verification_results.append(...)
        ↓
Reporter.run(history)   (unchanged)
```

Verification is deterministic. No LLM calls. No workspace modification. No `PatchPlan` generation.

---

# 2. VerificationResult Model

**Module:** `models/verification.py`

## `VerificationFinding`

| Field | Type | Description |
|-------|------|-------------|
| `category` | `str` | Rule category: `repository`, `environment`, `execution`, `output` |
| `code` | `str` | Machine-readable finding code |
| `message` | `str` | Human-readable description |

Frozen Pydantic model. No repair suggestions.

## `VerificationResult`

| Field | Type | Description |
|-------|------|-------------|
| `repository_status` | `str` | `PASS` or `FAIL` |
| `environment_status` | `str` | `PASS` or `FAIL` |
| `execution_status` | `str` | `PASS` or `FAIL` |
| `output_status` | `str` | `PASS` or `FAIL` |
| `overall_status` | `str` | `PASS` only when all categories pass |
| `findings` | `list[VerificationFinding]` | Structured collection of detected issues |

Frozen Pydantic model. Artifact only — no repair suggestions.

Constants: `VERIFICATION_PASS = "PASS"`, `VERIFICATION_FAIL = "FAIL"`.

---

# 3. VerificationService Design

**Module:** `services/verification_service.py`

## Public API

```python
class VerificationService:
    def verify(
        self,
        workspace: Workspace,
        execution_result: ExecutionResult,
    ) -> VerificationResult: ...
```

## Responsibilities

- Inspect workspace filesystem
- Inspect `ExecutionResult` fields
- Evaluate deterministic rules in four categories
- Build immutable `VerificationResult`

## Constraints

- Does not invoke `LLMProvider`
- Does not modify `Workspace`
- Does not generate `PatchPlan`
- Does not read repository source semantics

---

# 4. Reviewer Integration

**Module:** `agents/reviewer.py`

```python
class Reviewer:
    def __init__(self, verification_service: VerificationService | None = None) -> None: ...

    def run(
        self,
        workspace: Workspace,
        execution_result: ExecutionResult,
    ) -> VerificationResult:
        return self._verification_service.verify(workspace, execution_result)
```

Reviewer is a coordinator. `VerificationService` is injectable for testing.

**Previous behavior removed:** Stub `PatchPlan` return with `requires_patch=False`.

---

# 5. Workflow Integration

**Module:** `workflow/orchestrator.py`

After `Runner` completes:

1. Append `ExecutionResult` to `history.execution_results`
2. Call `Reviewer.run(history.workspace, execution_result)`
3. Append `VerificationResult` to `history.verification_results`
4. Continue to `Reporter` unchanged

**Removed:** Review loop with `PatchPlan` retry (`config.MAX_REVIEW_ITERATIONS`). M6.1 does not implement patch or retry logic. Single verification pass per workflow run.

**`WorkflowHistory` extended:**

```python
verification_results: list[VerificationResult] = Field(default_factory=list)
```

`WorkflowOrchestrator.run(paper_path) -> ReportModel` signature unchanged.

---

# 6. Repository Layout

Verification inspects the post-execution workspace:

```text
workspace/tasks/{paper_slug}/
├── .venv/                              (environment check)
├── src/                                (repository check)
├── configs/                            (repository check)
├── scripts/
│   └── train.py                        (repository + generated file check)
├── logs/
│   ├── environment_preparation.log     (environment check)
│   └── execution.log                   (execution check)
├── outputs/                            (output check)
├── README.md                           (repository check)
└── requirements.txt                    (repository check)
```

Verification reads filesystem state only. It does not create or delete files.

---

# 7. Module Exports

| Module | Addition |
|--------|----------|
| `models/__init__.py` | `VerificationFinding`, `VerificationResult` |
| `services/__init__.py` | `VerificationService` |

---

# 8. Out of Scope

| Item | Status |
|------|--------|
| `ReviewReport` | Not implemented |
| `PatchPlan` generation | Not implemented |
| LLM review | Not implemented |
| Automatic repair | Not implemented |
| Retry logic | Not implemented |
| Workflow review loop | Removed (was stub-only) |
| Semantic experiment quality validation | Not implemented |

---

# 9. Files Modified

| File | Change |
|------|--------|
| `models/verification.py` | **Created** — `VerificationFinding`, `VerificationResult` |
| `services/verification_service.py` | **Created** — deterministic verification rules |
| `agents/reviewer.py` | Delegates to `VerificationService` |
| `workflow/orchestrator.py` | Single verification stage; removed patch loop |
| `models/report.py` | `WorkflowHistory.verification_results` |
| `models/__init__.py` | Export verification models |
| `services/__init__.py` | Export `VerificationService` |
| `tests/test_verification.py` | **Created** — verification test module (not executed) |
| `docs/reviews/M6.1/design_review.md` | **Created** — this report |

---

# 10. Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| `VerificationResult` implemented | **YES** |
| `VerificationService` implemented | **YES** |
| Reviewer delegates verification | **YES** |
| Deterministic rule-based verification | **YES** |
| No LLM in verification | **YES** |
| `WorkflowOrchestrator.run()` preserved | **YES** |
| Workflow executable | **YES** (not re-tested this session) |
| All tests passing | **SKIPPED** |

---

# 11. Verification Flow

```text
VerificationService.verify(workspace, execution_result)
        │
        ├─ _verify_repository(workspace)
        │     ├─ REPOSITORY_SUBDIRS exist (src, configs, scripts, logs, outputs)
        │     ├─ README.md exists
        │     ├─ requirements.txt exists
        │     └─ scripts/train.py exists
        │
        ├─ _verify_environment(workspace)
        │     ├─ .venv/ directory exists
        │     ├─ logs/environment_preparation.log exists
        │     └─ log contains "Status: SUCCESS"
        │
        ├─ _verify_execution(workspace, execution_result)
        │     ├─ logs/execution.log exists
        │     ├─ execution_result.exit_code == 0
        │     └─ execution_result.executed_command is non-empty
        │
        ├─ _verify_outputs(workspace)
        │     ├─ outputs/ directory exists
        │     └─ EXPECTED_OUTPUT_FILES present (empty in M6.1)
        │
        └─ aggregate overall_status
              PASS if all categories PASS
              FAIL otherwise
```

Each category produces an independent `PASS`/`FAIL` status. All findings from failed checks are collected in `findings`.

---

# 12. Verification Rules

## Repository Integrity

| Rule ID | Check | Finding Code |
|---------|-------|--------------|
| R1 | Each directory in `REPOSITORY_SUBDIRS` exists | `missing_directory` |
| R2 | `README.md` exists | `missing_file` |
| R3 | `requirements.txt` exists | `missing_file` |
| R4 | `scripts/train.py` exists | `missing_generated_file` |

Source: `REPOSITORY_SUBDIRS` from `workspace.manager`; `REQUIRED_REPOSITORY_FILES` and `REQUIRED_GENERATED_FILES` in `verification_service.py`.

## Environment Status

| Rule ID | Check | Finding Code |
|---------|-------|--------------|
| E1 | `.venv/` directory exists | `missing_virtual_environment` |
| E2 | `logs/environment_preparation.log` exists | `missing_environment_log` |
| E3 | Log contains `Status: SUCCESS` | `environment_preparation_failed` |

## Execution Status

| Rule ID | Check | Finding Code |
|---------|-------|--------------|
| X1 | `logs/execution.log` exists | `missing_execution_log` |
| X2 | `execution_result.exit_code == 0` | `nonzero_exit_code` |
| X3 | `execution_result.executed_command` is non-empty | `missing_executed_command` |

## Expected Outputs

| Rule ID | Check | Finding Code |
|---------|-------|--------------|
| O1 | `outputs/` directory exists | `missing_outputs_directory` |
| O2 | Each path in `EXPECTED_OUTPUT_FILES` exists | `missing_output_file` |

`EXPECTED_OUTPUT_FILES` is an empty tuple in M6.1. No output file names are required beyond directory existence.

## Overall Status

| Rule | Logic |
|------|-------|
| OVR1 | `overall_status = PASS` iff all four category statuses are `PASS` |
| OVR2 | `overall_status = FAIL` if any category fails |

---

# 13. Verification Coverage

## Categories covered

| Category | `VerificationResult` field | Rules |
|----------|---------------------------|-------|
| Repository Integrity | `repository_status` | R1–R4 |
| Environment Status | `environment_status` | E1–E3 |
| Execution Status | `execution_status` | X1–X3 |
| Expected Outputs | `output_status` | O1–O2 |

## Inputs inspected

| Input | Fields / paths used |
|-------|---------------------|
| `Workspace` | `root_path` — all filesystem checks |
| `ExecutionResult` | `exit_code`, `executed_command` |

## Not covered in M6.1

| Area | Reason |
|------|--------|
| Source code correctness | Out of scope — no semantic validation |
| Config file validity | Out of scope |
| Training metrics / model quality | Out of scope |
| Output file content | `EXPECTED_OUTPUT_FILES` empty |
| LLM-based assessment | Explicitly excluded |
| Patch generation | Deferred to later milestones |

## Test module (not executed)

`tests/test_verification.py` defines coverage for:

- Successful verification
- Missing repository files
- Missing virtual environment
- Execution failure (non-zero exit code)
- Missing execution log
- Missing outputs directory
- Overall status aggregation
- Reviewer delegation
- Workflow verification pass and fail paths

Tests were not run in this session per project instruction.
