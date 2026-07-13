# Execution Planning Architecture

**Capability:** Execution Planning  
**Canonical output:** `ExecutionStrategy`  
**ADRs:** [ADR-0014](../adr/ADR-0014-Execution-Planning-Capability.md) · [ADR-0017](../adr/ADR-0017-Execution-Planning-Service-Architecture.md) · [ADR-0018](../adr/ADR-0018-Execution-Planning-Decision-Foundation.md)

---

## Purpose

Execution Planning commits an engineering strategy **before** task decomposition. It consumes read-only `PaperReproductionAnalysis` and `ResearchResourceDiscovery` and produces a single canonical `ExecutionStrategy`.

---

## Architecture

```text
ExecutionPlanningWorkflow          ← orchestration only
        ↓
Execution Planning Services        ← provider orchestration (execute)
        ↓
Provider Ports
        ↓
Embedded Providers                 ← runtime metadata + snapshot mapping
        ↓
Decision Foundation                ← internal reasoning (not exported)
        ↓
ExecutionStrategyBuilder         ← canonical assembly
        ↓
Validation
        ↓
ExecutionStrategy                  ← only exported artifact
```

---

## Six Engineering Stages

| Order | Stage | Service | Embedded provider |
|-------|-------|---------|-------------------|
| 1 | Strategy Decision | `StrategyService` | `EmbeddedStrategyProvider` |
| 2 | Resource Binding | `ResourceBindingService` | `EmbeddedResourceBindingProvider` |
| 3 | Reuse Planning | `ReuseService` | `EmbeddedReuseProvider` |
| 4 | Adaptation Planning | `AdaptationService` | `EmbeddedAdaptationProvider` |
| 5 | Generation Planning | `GenerationService` | `EmbeddedGenerationProvider` |
| 6 | Risk Assessment | `RiskService` | `EmbeddedRiskProvider` |

---

## Decision Foundation

Internal package: `providers/embedded/decision_foundation/`

```text
ObservedFacts          ← objective state from analysis + discovery
        ↓
DecisionDimensions     ← engineering evaluation dimensions (enum levels)
        ↓
decide_*()             ← per-stage engineering decisions
        ↓
Runtime Snapshots      ← workflow-internal stage outputs
```

| Module | Decision |
|--------|----------|
| `facts.py` | Observed facts extraction (assets + confidence contributions) |
| `dimensions.py` | Dimension evaluation (consumes explainable confidence) |
| `common.py` | Shared formatting helpers |
| `strategy_decision.py` | Strategy |
| `binding_decision.py` | Resource binding |
| `reuse_decision.py` | Reuse |
| `adaptation_decision.py` | Adaptation |
| `generation_decision.py` | Generation |
| `risk_decision.py` | Execution readiness + risk |

The Decision Foundation is **not** a public API. Planning also emits `DecisionTrace` and an **abstract** `ExecutionGraph` as separate runtime-persisted artifacts under `workspace/decision/`. The graph expresses stages and dependencies; it does not claim that backend commands or machine paths are available.

---

## Execution Graph (Phase 2)

`execution_planning/execution_graph.py` builds a deterministic dependency graph (clone → environment → dataset → checkpoints → config → training → evaluation → comparison) from strategy posture and discovery assets. This is planning output only — not execution. It must pass through Planning-to-Execution Materialization before submission to the Execution Engine.

---

## Boundaries

| Layer | Does | Does NOT |
|-------|------|----------|
| Workflow | Order stages, record provenance, invoke builder | Engineering reasoning |
| Services | Orchestrate providers, merge results | Mutate inputs, assemble canonical artifact |
| Providers | Build runtime snapshots from decisions | Bypass foundation, call workflow/builder |
| Decision Foundation | Deterministic engineering decisions | Network, LLM, code generation |
| Builder | Assemble and validate `ExecutionStrategy` | Engineering reasoning |
| Materialization handoff | Provide immutable strategy, graph, binding, and asset references | Resolve paths, generate commands, or assert backend readiness |

---

## Related Documentation

- Design: [execution-planning-workflow.md](../design/execution-planning-workflow.md)
- Phase audits: [reviews/5.1_execution_planning_workflow](../reviews/5.1_execution_planning_workflow/audit.md) through [6.6_execution_planning_risk_provider](../reviews/6.6_execution_planning_risk_provider/audit.md)
- Stabilization: [reviews/6.7_execution_planning_architecture_stabilization](../reviews/6.7_execution_planning_architecture_stabilization/audit.md)
- Executable handoff: [EXECUTION_MATERIALIZATION.md](EXECUTION_MATERIALIZATION.md)
