# Decision Quality Improvement — Phase 2 Audit

**Project:** Man1Lab  
**Phase:** Decision Quality Improvement Phase 2  
**Scope:** Research Asset model, explainable confidence, decision trace, execution graph, workspace persistence, Golden Benchmarks  
**Date:** 2026-07-09  
**Status:** Implemented

---

## 1. Objective

Extend Phase 1 decision quality improvements with:

1. Unified **Research Asset** pipeline (repository is one asset type among ten).
2. **Explainable confidence** replacing opaque single-number selection confidence.
3. **DecisionTrace** canonical artifact tracing decisions through discovery and planning stages.
4. **ExecutionGraph** deterministic planning output for a future execution engine.
5. Runtime workspace persistence for `decision/` artifacts.
6. Extended Golden Benchmarks guarding regressions.

**Constraints honored:** No Runtime/Session/Providers/Console redesign; no Execute implementation; no public API changes; canonical models extended backward-compatibly.

---

## 2. Architecture Impact

### 2.1 Discovery Layer

| Change | Location | Impact |
|--------|----------|--------|
| **Research Asset model** | `models/research_resource_discovery.py` | `ResearchAssetType`, `ResearchAsset`, `ResearchAssetCollection` added; `research_assets` field on `ResearchResourceDiscovery` |
| **Asset builder** | `discovery/assets.py` | Maps `RepositoryCandidate` → `ResearchAsset` with selection markers |
| **Explainable confidence** | `models/explainable_confidence.py`, `discovery/confidence.py` | `SelectionRecord.confidence_composition` with per-signal contributions |
| **Selection integration** | `discovery/selection.py` | Uses `compose_selection_confidence()`; preserves Phase 1 floors via `max(legacy_floor, weighted_sum)` |
| **Discovery decision trace** | `discovery/decision_trace.py` | Stages: Repository → Evidence → Verification → Ranking → Selection |

### 2.2 Execution Planning Layer

| Change | Location | Impact |
|--------|----------|--------|
| **Facts consume assets + confidence** | `providers/embedded/decision_foundation/facts.py` | `selected_assets`, `confidence_contributions`, per-selection `confidence_composition` |
| **Dimensions use confidence** | `providers/embedded/decision_foundation/dimensions.py` | `resource_reliability` and `reuse_opportunity` factor contribution scores |
| **Planning decision trace** | `execution_planning/decision_trace.py` | Adds Binding → Reuse → Generation → Risk stages |
| **Execution graph** | `execution_planning/execution_graph.py` | Deterministic stage graph from posture, bindings, and assets |

### 2.3 Runtime Layer

| Change | Location | Impact |
|--------|----------|--------|
| **Workspace persistence** | `runtime/session/workspace_store.py` | `decision/decision_trace.json`, `.md`, `execution_graph.json`, `.md` |
| **Persistence hooks** | `runtime/session/decision_artifacts.py` | `importlib` lazy load — preserves runtime boundary (no static discovery imports) |
| **Console wiring** | `runtime/console/builtins.py` | Persists decision artifacts after `discover` / `plan` |

No changes to `ExecutionPlanningWorkflow` stage order, facade signatures, or `ExecutionStrategy` schema.

---

## 3. Research Asset Architecture

```text
RepositoryCandidate (canonical, unchanged)
        ↓
build_research_assets()
        ↓
ResearchAssetCollection
  ├── asset_type: repository | checkpoint_weights | dataset | ...
  ├── selected_primary / selected_fallback
  └── confidence_composition
        ↓
Planning ObservedFacts.selected_assets
```

**Asset types supported:** Repository, Checkpoint/Weights, Dataset, Configuration, Docker Image, Environment, Requirements, Documentation, Benchmark, Evaluation Script.

**Backward compatibility:** Legacy `ResearchResourceDiscovery` JSON without `research_assets` validates with empty collection. `RepositoryCandidate` and `SelectionRecord.confidence` unchanged.

---

## 4. Confidence Architecture

```text
Evidence + Verification + Ranking + Officiality
        ↓
compose_selection_confidence()
        ↓
ExplainableConfidence
  ├── overall (deterministic, matches SelectionRecord.confidence)
  └── contributions[] (official_organization, paper_match, readme_match,
                      verification, recent_activity, checkpoint_availability,
                      ranking_score)
        ↓
Planning: facts.confidence_contributions → dimensions → strategy
```

**Composition rule:** `max(legacy_verification_floor, weighted_sum_capped)` — preserves Phase 1 confidence floors while exposing auditable signal breakdown.

---

## 5. Decision Trace

Canonical model: `models/decision_trace.py` (`DecisionTrace`, `DecisionStageRecord`).

| Stage | Recorded |
|-------|----------|
| Repository | Candidate/asset counts, collection rule |
| Evidence | Evidence count |
| Verification | Pass/partial counts |
| Ranking | Eligible candidate counts |
| Selection | Primary selection count, gaps |
| Binding | Binding count, anchor |
| Reuse | Reuse mode |
| Generation | Generation scope |
| Risk | Blocking risks, overall confidence |

Persisted: `workspace/decision/decision_trace.json` and `.md`.

---

## 6. Execution Graph

Canonical model: `models/execution_graph.py` (`ExecutionGraph`, `ExecutionGraphNode`).

**Typical stages (posture-dependent):**

Clone Repository → Prepare Environment → Download Dataset → Download Checkpoints → Generate Config → Training → Evaluation → Comparison

GREENFIELD omits clone; HYBRID includes checkpoint download when applicable.

Persisted: `workspace/decision/execution_graph.json` and `.md`.

---

## 7. Benchmark Coverage

| Benchmark | Phase 2 assertions |
|-----------|-------------------|
| `resnet_official` | Research asset selection, confidence contributions, decision trace stages, execution graph with clone |
| `attention_official` | Same |
| `community_fork` | Asset + trace + graph |
| `hybrid_missing_checkpoint` | Asset + trace + graph |
| `greenfield_no_resources` | Trace + graph (no clone node) |
| Phase 1 fixtures (`tests/benchmarks/fixtures.py`) | Unchanged posture/binding/reuse assertions |

**Regression guards:**

- Confidence floor preserved (legacy floor in composition)
- Decision trace must include Selection + Binding stages
- Execution graph must not disappear for benchmark cases
- Repository asset `selected_primary` when repository selected

**Test results:** 816 tests passed (804 baseline + 12 Phase 2 tests), 8 golden subtests passed.

---

## 8. Files Changed / Added

### Added

- `models/explainable_confidence.py`
- `models/decision_trace.py`
- `models/execution_graph.py`
- `models/research_asset.py` (re-exports)
- `discovery/assets.py`
- `discovery/confidence.py`
- `discovery/decision_trace.py`
- `execution_planning/decision_trace.py`
- `execution_planning/execution_graph.py`
- `runtime/session/decision_artifacts.py`
- `tests/test_research_assets.py`
- `tests/test_explainable_confidence.py`
- `tests/test_decision_trace.py`
- `tests/test_execution_graph.py`
- `tests/test_decision_quality_phase2_boundary.py`
- `docs/reviews/decision_quality_improvement_phase_2/audit.md`

### Modified

- `models/research_resource_discovery.py`
- `discovery/selection.py`
- `discovery/workflow.py`
- `providers/embedded/decision_foundation/facts.py`
- `providers/embedded/decision_foundation/dimensions.py`
- `providers/embedded/decision_foundation/strategy_decision.py`
- `runtime/session/workspace_store.py`
- `runtime/console/builtins.py`
- `tests/test_decision_quality_benchmarks.py`
- `tests/test_console_workspace.py`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/RUNTIME.md`
- `docs/architecture/EXECUTION_PLANNING.md`
- `docs/CURRENT_STATUS.md`

---

## 9. Remaining Work (Execution Engine Foundation)

| Item | Priority | Notes |
|------|----------|-------|
| Execution graph → task decomposition | P1 | Map `ExecutionGraphNode` to `TaskModel` steps |
| Runner consumes decision trace | P2 | Correlate execution events with trace stages |
| Asset-type-specific binding roles | P2 | Extend binding beyond repository/checkpoint/dataset |
| GitHub-backed golden benchmarks | P1 | Network-isolated fixtures (from Phase 1 backlog) |
| Manual override in selection trace | P3 | Schema reserved; trace stage for overrides not implemented |
| Execute stage | Out of scope | Graph is planning-only until Execution Engine Foundation |

---

## 10. Summary

Phase 2 generalizes Discovery from repository-centric to a unified Research Asset pipeline, adds explainable confidence consumed by Planning dimensions and strategy notes, and introduces `DecisionTrace` and `ExecutionGraph` as runtime-persisted artifacts. Golden Benchmarks and boundary tests guard confidence floors, trace completeness, and graph stability without changing public APIs or Execute scope.
