# Design Review Report — M6.3 Patch Planning

**Milestone:** M6.3 — Patch Planning  
**Capability:** Reviewer / Patch Planning  
**Status:** Complete  
**Tests:** 98 total, all passing

---

# 1. Patch Planning Pipeline

Complete patch planning path after LLM review:

```text
ReviewReport
        ↓
PatchPlanner.plan(review_report)
        ↓
PromptBuilder.build_patch_planner_prompt()
        ↓
LLMProvider.complete(messages)
        ↓
ResponseParser.parse(raw_response)
        ↓
build_patch_plan(extracted)
        ↓
PatchPlan
        ↓
history.patch_plans.append(...)
```

Patch planning consumes `ReviewReport` only. It does not inspect repositories or propose code changes.

---

# 2. PatchPlan Model

**Module:** `models/review.py`

| Field | Type | Description |
|-------|------|-------------|
| `requires_patch` | `bool` | Whether another workflow iteration is required |
| `priority` | `str` | `LOW`, `MEDIUM`, or `HIGH` |
| `targets` | `list[str]` | Workflow areas needing attention (e.g. `execution`) |
| `reason` | `str` | Workflow decision rationale |
| `strategy` | `str` | Workflow continuation strategy |

Frozen Pydantic model. Workflow artifact only — no source code, file diffs, or edit instructions.

**Removed from prior stub:** `PatchItem`, `patches`, `analysis` fields.

---

# 3. Validation Layer

**Module:** `validation/patch.py`

| Function | Purpose |
|----------|---------|
| `validate_patch_dict(data)` | Required fields and type checks |
| `normalize_patch_dict(data)` | Normalize bool, priority, targets, strings |
| `build_patch_plan(data)` | Validate → normalize → construct `PatchPlan` |

**Exception:** `PatchValidationError` in `validation/exceptions.py`

**`priority` allowed values:** `LOW`, `MEDIUM`, `HIGH` (case-insensitive input, normalized to uppercase)

---

# 4. PatchPlanner Design

**Module:** `planning/patch_planner.py`

```python
class PatchPlanner:
    def __init__(
        self,
        prompt_builder: PromptBuilder | None = None,
        llm: LLMProvider | None = None,
        response_parser: ResponseParser | None = None,
    ) -> None: ...

    def plan(self, review_report: ReviewReport) -> PatchPlan: ...
```

**Dependencies:** `PromptBuilder`, `LLMProvider` (default `MockLLMProvider(MOCK_PATCH_NO_ITERATION_JSON)`), `ResponseParser`

User message contains `ReviewReport` JSON only.

---

# 5. Reviewer Integration

**Module:** `agents/reviewer.py`

Reviewer retains M6.2 `run()` for `ReviewReport` generation. M6.3 adds:

```python
def plan_patch(self, review_report: ReviewReport) -> PatchPlan:
    return self._patch_planner.plan(review_report)
```

`PatchPlanner` is injectable via `Reviewer.__init__(patch_planner=...)`.

Orchestrator calls `PatchPlanner` directly; `Reviewer.plan_patch()` provides the integration path for tests and future composition.

---

# 6. Workflow Integration

**Module:** `workflow/orchestrator.py`

Review loop restored with `config.MAX_REVIEW_ITERATIONS`:

```text
for _ in range(MAX_REVIEW_ITERATIONS):
    VerificationService.verify(...)
    Reviewer.run(...) → ReviewReport
    PatchPlanner.plan(...) → PatchPlan
    if not patch_plan.requires_patch:
        break
    if patch_plan.requires_patch:
        pass  # iteration deferred
    break
```

| Behavior | M6.3 |
|----------|------|
| Loop structure | Restored |
| `requires_patch=False` | Breaks loop, proceeds to Reporter |
| `requires_patch=True` | Enters branch, no Coder/Runner re-execution |
| Multiple iterations | Prevented by explicit `break` after first cycle |
| Coder/Runner retry | Not implemented (deferred) |

**New pipeline stage:** `PipelineStage.PATCH_PLANNER = "PatchPlanner"`

**Optional constructor parameter:** `patch_planner: PatchPlanner | None = None`

`WorkflowOrchestrator.run(paper_path) -> ReportModel` signature unchanged.

---

# 7. Prompt Infrastructure

**Prompt files:** `prompts/patch_planner/`

| File | Purpose |
|------|---------|
| `system.md` | Workflow decision role; no code changes |
| `extraction.md` | Analyze ReviewReport for iteration decision |
| `schema.md` | JSON output schema |
| `examples.md` | No-iteration and iteration-required examples |

**PromptBuilder:** `build_patch_planner_prompt()`

---

# 8. Mock LLM Support

**Module:** `llm/mock_provider.py`

| Constant | Use |
|----------|-----|
| `MOCK_PATCH_NO_ITERATION_JSON` | Default; `requires_patch: false` |
| `MOCK_PATCH_ITERATION_JSON` | `requires_patch: true` with execution target |

---

# 9. Downstream Updates

| File | Change |
|------|--------|
| `workspace/manager.py` | README uses `patch_plan.reason`; report uses priority/reason/strategy |
| `agents/reporter.py` | Unchanged; `debugging_history` still maps from `patch_plans` |

---

# 10. Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| `PatchPlan` implemented | **YES** |
| `PatchPlanner` implemented | **YES** |
| Validation implemented | **YES** |
| Workflow branch restored | **YES** |
| No repeated execution | **YES** |
| `WorkflowOrchestrator.run()` preserved | **YES** |
| Workflow executable | **YES** |
| All tests passing | **YES** (98) |

---

# 11. Patch Planning Flow

```text
ReviewReport
        ↓
PatchPlanner.plan(review_report)
        │
        ├─ build_patch_planner_prompt()
        │     system + extraction + schema + examples
        │
        ├─ LLMMessage(system, prompt)
        ├─ LLMMessage(user, ReviewReport JSON)
        │
        ├─ llm.complete(messages, temperature=0.0)
        ├─ response_parser.parse(raw_response) → dict
        └─ build_patch_plan(dict) → PatchPlan
```

The LLM receives `ReviewReport` as the sole input artifact. It does not receive workspace paths, file contents, or verification logs directly.

---

# 12. Workflow Branch Logic

```text
Runner → ExecutionResult
        ↓
[review loop — max MAX_REVIEW_ITERATIONS]
        │
        ├─ VerificationService.verify() → VerificationResult
        ├─ Reviewer.run() → ReviewReport
        ├─ PatchPlanner.plan() → PatchPlan
        │
        ├─ if not patch_plan.requires_patch:
        │       break → Reporter
        │
        └─ if patch_plan.requires_patch:
                pass  (iteration branch — execution deferred)
                break → Reporter
```

| Scenario | `requires_patch` | Coder/Runner re-run | Loop iterations |
|----------|------------------|---------------------|-----------------|
| Success path | `false` | No | 1 |
| Failure path (M6.3) | `true` | No | 1 |
| Future integration | `true` | Yes (deferred) | Up to `MAX_REVIEW_ITERATIONS` |

M6.3 always exits the loop after one planning cycle to prevent infinite loops and deferred re-execution.

---

# 13. PatchPlan Schema

## JSON output (LLM)

```json
{
  "requires_patch": false,
  "priority": "LOW | MEDIUM | HIGH",
  "targets": ["workflow area strings"],
  "reason": "string",
  "strategy": "string"
}
```

## Validation rules

| Field | Rule |
|-------|------|
| `requires_patch` | Required boolean |
| `priority` | Required non-empty string; normalized to uppercase; must be `LOW`, `MEDIUM`, or `HIGH` |
| `targets` | Required list of non-empty strings (may be empty) |
| `reason` | Required non-empty string |
| `strategy` | Required non-empty string |

## Pydantic model

```python
class PatchPlan(BaseModel):
    model_config = ConfigDict(frozen=True)
    requires_patch: bool
    priority: str
    targets: list[str]
    reason: str
    strategy: str
```

## Construction path

```text
LLM raw response
        ↓
ResponseParser.parse() → dict
        ↓
validate_patch_dict(dict)
        ↓
normalize_patch_dict(dict)
        ↓
PatchPlan(**normalized)
```

Direct construction from raw dictionaries without validation is not used in the PatchPlanner path.

## Workflow targets (examples)

| Target value | Meaning |
|--------------|---------|
| `repository` | Repository integrity category |
| `environment` | Environment preparation category |
| `execution` | Script execution category |
| `output` | Output artifacts category |

Targets describe workflow areas, not file paths.
