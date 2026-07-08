# ADR-0017 — Execution Planning Service Architecture

## Status

Accepted

## Date

2026-07-08

## Context

[ADR-0014](ADR-0014-Execution-Planning-Capability.md) records **Execution Planning** as the third Platform Capability and defines the capability boundary (`ExecutionStrategy` as canonical output). Phase 5.1 introduced `ExecutionPlanningWorkflow` as the permanent coordinator. Phase 5.2 completed the **service / port / provider foundation**, mirroring the Discovery capability layering established in v1.2.

Without a recorded service architecture, implementers might place engineering reasoning in the workflow, services, or builder — violating layer boundaries and blocking provider substitution.

## Decision

Adopt a **six-layer internal architecture** for Execution Planning:

```text
ExecutionPlanningWorkflow
        ↓
Execution Planning Services
        ↓
Provider Ports
        ↓
Embedded Providers
        ↓
Decision Foundation
        ↓
ExecutionStrategyBuilder
        ↓
Validation
        ↓
ExecutionStrategy
```

See [ADR-0018](ADR-0018-Execution-Planning-Decision-Foundation.md) for the Decision Foundation architecture.

### Layer responsibilities

| Layer | Owns | Does NOT own |
|-------|------|--------------|
| **Workflow** | Stage ordering, timestamps, provenance envelope, builder invocation | Provider calls, engineering reasoning, canonical assembly |
| **Services** | Provider orchestration, ordering, per-stage merge | Workflow scheduling, artifact assembly, cross-capability I/O |
| **Ports** | Provider contracts | Implementation |
| **Providers** | Stage runtime metadata; map decision outputs to snapshots | Workflow orchestration, service merge policy, builder logic |
| **Decision Foundation** | Shared facts, dimensions, and per-stage engineering decisions | Public API exposure; networking; code generation |
| **Builder** | Canonical `ExecutionStrategy` assembly from runtime results | Engineering decisions |
| **Validation** | Structural correctness of assembled artifact | Strategy inference |

### Interface convention

All Execution Planning **service** and **provider** methods use **`execute(...)`** — not `plan()`.

### Six stages (fixed order)

| Order | Stage | Service | Provider port |
|-------|-------|---------|---------------|
| 1 | Strategy Decision | `StrategyService` | `StrategyProvider` |
| 2 | Resource Binding | `ResourceBindingService` | `ResourceBindingProvider` |
| 3 | Reuse Planning | `ReuseService` | `ReuseProvider` |
| 4 | Adaptation Planning | `AdaptationService` | `AdaptationProvider` |
| 5 | Generation Planning | `GenerationService` | `GenerationProvider` |
| 6 | Risk Assessment | `RiskService` | `RiskProvider` |

Assembly follows Stage 6: `ExecutionStrategyBuilder.build(risk_result, ...)`.

### Provider hierarchy (default)

```text
Embedded*Provider  →  NoOp*Provider
```

| Provider type | Behavior |
|---------------|----------|
| Embedded | Deterministic engineering decisions via Decision Foundation |
| NoOp | Empty/default runtime results |

### Artifact boundary

| Type | Visibility |
|------|------------|
| Runtime stage models (`*Result`, `*Snapshot`) | Internal to Execution Planning — never exported |
| `ExecutionStrategy` | **Only** artifact exported from the capability |

### Dependency rules

| Rule | Enforcement |
|------|-------------|
| Workflow → Services only | Workflow must not import providers |
| Services → Ports + Providers | Services orchestrate; they do not assemble canonical artifacts |
| Builder independent | Builder receives runtime results; no provider calls |
| Inputs read-only | `PaperReproductionAnalysis` and `ResearchResourceDiscovery` are not mutated |

## Alternatives

**Reasoning in workflow coordinator:** Rejected. Violates orchestration-only boundary; blocks provider substitution and testing.

**Reasoning in services:** Rejected. Services own orchestration and merge — not engineering decisions. Mirrors Discovery where services delegate to providers.

**Reasoning in builder:** Rejected. Builder is assembly-only; mixing decisions with artifact construction prevents audit of stage outputs.

**Single monolithic planner function:** Rejected. Six semantic stages have distinct failure modes and runtime contracts ([execution-planning-workflow.md](../design/execution-planning-workflow.md)).

## Consequences

**Positive:**

- **Mirrors Discovery** — consistent ports & adapters pattern across platform capabilities
- **Provider substitution** — new reasoning backends plug in per stage without workflow changes
- **Testable boundaries** — workflow, services, providers, and builder tested independently
- **Clear maturity path** — embedded providers complete in v1.2.1

**Negative:**

- **More modules** — six services, six ports, twelve default providers, decision foundation package

## Relationship to Other ADRs

- [ADR-0014](ADR-0014-Execution-Planning-Capability.md): Capability boundary and `ExecutionStrategy` contract — this ADR implements internal structure only
- [ADR-0018](ADR-0018-Execution-Planning-Decision-Foundation.md): Shared internal decision foundation
- [ADR-0013](ADR-0013-Research-Resource-Discovery.md): Discovery service architecture is the reference pattern
- [ADR-0001](ADR-0001-Workflow-Orchestrator.md): Platform coordinator invokes `ExecutionPlanningWorkflow`; does not call services or providers directly

Companion design: [execution-planning-workflow.md](../design/execution-planning-workflow.md)

Phase audits: [5.1_execution_planning_workflow](../reviews/5.1_execution_planning_workflow/audit.md), [5.2_execution_planning_services](../reviews/5.2_execution_planning_services/audit.md)
