# Design Review Report — M6.2 LLM Review

**Milestone:** M6.2 — LLM Review  
**Capability:** Reviewer / LLM Review  
**Status:** Complete  
**Tests:** 87 total, all passing

---

# 1. Review Pipeline

Complete LLM review path after deterministic verification:

```text
PaperModel
        ×
TaskModel
        ×
VerificationResult
        ↓
WorkflowOrchestrator
        ↓
Reviewer.run(paper, task, verification_result)
        ↓
PromptBuilder.build_reviewer_prompt()
        ↓
LLMProvider.complete(messages)
        ↓
ResponseParser.parse(raw_response)
        ↓
build_review_report(extracted)
        ↓
ReviewReport
        ↓
history.review_reports.append(...)
        ↓
Reporter.run(history)   (unchanged)
```

Deterministic verification (M6.1) runs before the Reviewer stage via `VerificationService` in the orchestrator. The Reviewer stage performs LLM analysis only.

---

# 2. ReviewReport Model

**Module:** `models/review_report.py`

| Field | Type | Description |
|-------|------|-------------|
| `summary` | `str` | Brief reproduction status summary |
| `analysis` | `str` | Detailed explanation of verification outcome |
| `identified_issues` | `list[str]` | Issues derived from verification findings |
| `strengths` | `list[str]` | Successful aspects of reproduction |
| `risk_level` | `str` | `LOW`, `MEDIUM`, or `HIGH` |
| `next_action` | `str` | Status-oriented next step (no repair instructions) |

Frozen Pydantic model. Analysis artifact only — no patches or repair instructions.

---

# 3. Validation Layer

**Module:** `validation/review.py`

Follows the same pattern as `validation/paper.py` and `validation/task.py`:

| Function | Purpose |
|----------|---------|
| `validate_review_dict(data)` | Required fields and type checks |
| `normalize_review_dict(data)` | Trim strings, uppercase `risk_level`, normalize lists |
| `build_review_report(data)` | Validate → normalize → construct `ReviewReport` |

**Exception:** `ReviewValidationError` in `validation/exceptions.py`

**`risk_level` allowed values:** `LOW`, `MEDIUM`, `HIGH` (case-insensitive input, normalized to uppercase)

---

# 4. Reviewer Integration

**Module:** `agents/reviewer.py`

```python
class Reviewer:
    def __init__(
        self,
        prompt_builder: PromptBuilder | None = None,
        llm: LLMProvider | None = None,
        response_parser: ResponseParser | None = None,
    ) -> None: ...

    def run(
        self,
        paper: PaperModel,
        task: TaskModel,
        verification_result: VerificationResult,
    ) -> ReviewReport: ...
```

**Dependencies:** `PromptBuilder`, `LLMProvider` (default `MockLLMProvider`), `ResponseParser`

**Previous behavior removed:** Delegation to `VerificationService` (moved to orchestrator).

**Ground truth constraint:** User message includes `PaperModel`, `TaskModel`, and `VerificationResult` JSON only. No workspace paths or filesystem state.

---

# 5. Workflow Integration

**Module:** `workflow/orchestrator.py`

After `Runner` completes:

1. `VerificationService.verify(workspace, execution_result)` → append to `history.verification_results`
2. `Reviewer.run(paper, task, verification_result)` → append to `history.review_reports`
3. `Reporter.run(history)` unchanged

**`WorkflowHistory` extended:**

```python
review_reports: list[ReviewReport] = Field(default_factory=list)
```

**Optional constructor parameter:** `verification_service: VerificationService | None = None`

`WorkflowOrchestrator.run(paper_path) -> ReportModel` signature unchanged.

---

# 6. Prompt Infrastructure

**Prompt files:** `prompts/reviewer/`

| File | Purpose |
|------|---------|
| `system.md` | Agent role; trust VerificationResult; no patches |
| `extraction.md` | Analysis instructions |
| `schema.md` | JSON output schema |
| `examples.md` | PASS and FAIL examples |

**PromptBuilder:** `build_reviewer_prompt()` — combines system, extraction, schema, examples in order.

---

# 7. Mock LLM Support

**Module:** `llm/mock_provider.py`

| Constant | Use |
|----------|-----|
| `MOCK_REVIEWER_PASS_JSON` | Default mock for successful verification review |
| `MOCK_REVIEWER_FAIL_JSON` | Mock for failed verification review |

No external API calls in tests.

---

# 8. Out of Scope

| Item | Status |
|------|--------|
| `PatchPlan` generation | Not implemented |
| Retry loop | Not implemented |
| Workflow repair | Not implemented |
| Automatic code modification | Not implemented |
| Execution re-run | Not implemented |
| Independent filesystem inspection by LLM | Not implemented |

---

# 9. Files Modified

| File | Change |
|------|--------|
| `models/review_report.py` | **Created** — `ReviewReport` |
| `validation/review.py` | **Created** — validation layer |
| `validation/exceptions.py` | `ReviewValidationError` |
| `validation/__init__.py` | Export review validation |
| `agents/reviewer.py` | LLM review via `build_review_report` |
| `workflow/orchestrator.py` | VerificationService + Reviewer stages |
| `models/report.py` | `WorkflowHistory.review_reports` |
| `models/__init__.py` | Export `ReviewReport` |
| `prompt/builder.py` | `build_reviewer_prompt()` |
| `prompts/reviewer/*.md` | Review prompt sections |
| `llm/mock_provider.py` | Review mock JSON constants |
| `tests/test_review.py` | **Created** — review tests |
| `tests/test_verification.py` | Updated workflow tests |
| `docs/reviews/M6.2/design_review.md` | **Created** — this report |

---

# 10. Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| `ReviewReport` model implemented | **YES** |
| Reviewer produces `ReviewReport` | **YES** |
| `VerificationResult` used as ground truth | **YES** |
| Validation implemented | **YES** |
| `WorkflowOrchestrator.run()` preserved | **YES** |
| Workflow executable | **YES** |
| All tests passing | **YES** (87) |

---

# 11. Review Flow

```text
VerificationService.verify(workspace, execution_result)
        ↓
VerificationResult  (deterministic, M6.1)
        ↓
Reviewer.run(paper, task, verification_result)
        │
        ├─ build_reviewer_prompt()
        │     system + extraction + schema + examples
        │
        ├─ LLMMessage(system, prompt)
        ├─ LLMMessage(user, paper + task + VerificationResult JSON)
        │
        ├─ llm.complete(messages, temperature=0.0)
        ├─ response_parser.parse(raw_response) → dict
        └─ build_review_report(dict) → ReviewReport
```

The LLM receives `VerificationResult` labeled as ground truth in the user message. It does not receive workspace paths, file contents, or execution logs directly.

---

# 12. Review Prompt Strategy

## System prompt

- Defines Reviewer as analysis agent for verification outcomes
- Mandates `VerificationResult` as sole source of truth
- Prohibits independent file inspection and code modification proposals

## Extraction prompt

- Instructs explanation of passed/failed categories
- Uses `PaperModel` and `TaskModel` as background context only
- Bases conclusions on `VerificationResult` fields and `findings`

## Schema prompt

- Defines six JSON fields for `ReviewReport`
- Explicitly excludes patches and repair instructions

## Examples prompt

- PASS example: all categories pass, `risk_level: LOW`, empty `identified_issues`
- FAIL example: execution failure, `risk_level: HIGH`, populated `identified_issues`

## Temperature

`0.0` — consistent with Reader and Planner agents.

---

# 13. ReviewReport Schema

## JSON output (LLM)

```json
{
  "summary": "string",
  "analysis": "string",
  "identified_issues": ["string"],
  "strengths": ["string"],
  "risk_level": "LOW | MEDIUM | HIGH",
  "next_action": "string"
}
```

## Validation rules

| Field | Rule |
|-------|------|
| `summary` | Required non-empty string |
| `analysis` | Required non-empty string |
| `identified_issues` | Required list of non-empty strings (may be empty) |
| `strengths` | Required list of non-empty strings (may be empty) |
| `risk_level` | Required; normalized to uppercase; must be `LOW`, `MEDIUM`, or `HIGH` |
| `next_action` | Required non-empty string |

## Pydantic model

```python
class ReviewReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    summary: str
    analysis: str
    identified_issues: list[str]
    strengths: list[str]
    risk_level: str
    next_action: str
```

## Construction path

```text
LLM raw response
        ↓
ResponseParser.parse() → dict
        ↓
validate_review_dict(dict)
        ↓
normalize_review_dict(dict)
        ↓
ReviewReport(**normalized)
```

Direct construction from raw dictionaries without validation is not used in the Reviewer agent path.
