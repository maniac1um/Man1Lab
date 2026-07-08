# ADR-0018 — Execution Planning Decision Foundation

## Status

Accepted

## Date

2026-07-08

## Context

[ADR-0014](ADR-0014-Execution-Planning-Capability.md) defines Execution Planning as a Platform Capability. [ADR-0017](ADR-0017-Execution-Planning-Service-Architecture.md) defines the service and provider layering. Phase 6 introduced six embedded engineering decision providers that share internal reasoning abstractions.

Without a recorded decision foundation architecture, future providers might duplicate facts extraction, dimension evaluation, or engineering rules — violating layer boundaries and making the capability harder to maintain.

## Decision

Adopt a **shared internal Decision Foundation** inside embedded Execution Planning providers:

```text
ObservedFacts
        ↓
DecisionDimensions
        ↓
Engineering Decisions (per stage)
        ↓
Runtime Snapshots
        ↓
ExecutionStrategy (via Builder)
```

The permanent Execution Planning architecture is:

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
ExecutionStrategy
```

The Decision Foundation is **internal only**. It is not a canonical artifact, public API, or workflow stage.

## Responsibilities

### Workflow

- Fixed stage ordering
- Timestamp and provenance envelope
- Service orchestration only
- Builder invocation after risk assessment

### Services

- Provider orchestration per stage
- Per-stage merge policy
- No engineering reasoning

### Providers

- Stage runtime metadata (`started_at`, `completed_at`, warnings, diagnostics)
- Map decision outputs to runtime snapshots
- Delegate engineering reasoning to the Decision Foundation

### Decision Foundation

| Module | Responsibility |
|--------|----------------|
| `facts.py` | Immutable observed state from analysis and discovery |
| `dimensions.py` | Engineering evaluation dimensions (enum levels only) |
| `common.py` | Shared formatting helpers (no engineering decisions) |
| `strategy_decision.py` | Strategy engineering decision |
| `binding_decision.py` | Resource binding decision |
| `reuse_decision.py` | Reuse planning decision |
| `adaptation_decision.py` | Adaptation authorization decision |
| `generation_decision.py` | Generation planning decision |
| `risk_decision.py` | Execution readiness assessment and risk decision |

### Builder

- Deterministic assembly from final runtime result
- Canonical `ExecutionStrategy` publication
- Structural validation only

## Engineering Decisions

Execution Planning commits six engineering decisions in fixed order:

| Stage | Decision | Output snapshot |
|-------|----------|-----------------|
| 1 Strategy | Engineering posture and scope | `StrategyDecisionSnapshot` |
| 2 Binding | Resource roles from discovery selections | `ResourceBindingSnapshot` |
| 3 Reuse | Reuse commitments per binding | `ReusePlanSnapshot` |
| 4 Adaptation | Authorized modification scope | `AdaptationPlanSnapshot` |
| 5 Generation | Engineering artifact generation plan | `GenerationPlanSnapshot` |
| 6 Risk | Execution readiness and residual risks | `RiskAssessmentSnapshot` |

Each decision consumes prior stage outputs plus shared facts and dimensions. Later stages do not re-derive earlier engineering commitments.

## Architecture Boundaries

| Layer | Must NOT |
|-------|----------|
| Workflow | Contain engineering rules; call providers directly; assemble canonical artifacts |
| Services | Contain engineering rules; bypass providers |
| Providers | Bypass Decision Foundation; mutate inputs; call workflow or builder |
| Decision Foundation | Expose canonical artifacts; perform networking; generate code or files |
| Builder | Perform engineering reasoning; reorder stages |

## Alternatives

| Alternative | Why not |
|-------------|---------|
| Engineering rules in each provider independently | Duplication and inconsistent decisions |
| Engineering rules in services | Services become reasoning engines; harder to substitute providers |
| Engineering rules in workflow | Violates orchestration-only boundary |
| Decision Foundation as public API | Leaks internal reasoning; couples consumers to implementation |

## Consequences

**Positive**

- Single facts extraction and dimension evaluation path
- Consistent engineering decision ordering
- Providers remain thin adapters over deterministic decisions
- Future provider variants can reuse the foundation unchanged

**Negative**

- Internal module coupling within embedded providers
- Decision foundation modules must remain provider-independent

## Related ADRs

- [ADR-0014](ADR-0014-Execution-Planning-Capability.md) — capability boundary
- [ADR-0017](ADR-0017-Execution-Planning-Service-Architecture.md) — service architecture
