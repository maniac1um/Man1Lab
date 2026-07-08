# Architecture Decision Records (ADR)

## What is an ADR?

An Architecture Decision Record (ADR) documents a significant architectural decision: the context, the choice made, alternatives considered, and consequences.

ADRs provide a durable audit trail for why the codebase is structured the way it is.

## When to create a new ADR

Create an ADR when a decision:

- Changes a public interface covered by the architecture freeze
- Introduces a new cross-cutting module or pattern
- Alters agent communication or workflow scheduling
- Replaces a previously accepted approach

Do not create an ADR for routine bug fixes, internal refactors that preserve interfaces, or milestone scope that already follows an existing ADR.

## ADR Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0001](ADR-0001-Workflow-Orchestrator.md) | Workflow Orchestrator | Accepted |
| [ADR-0002](ADR-0002-Stable-Reader-Interface.md) | Stable Reader Interface | Accepted |
| [ADR-0003](ADR-0003-Prompt-Infrastructure.md) | Prompt Infrastructure | Accepted |
| [ADR-0004](ADR-0004-Planning-Strategy.md) | Planning Strategy | Accepted |
| [ADR-0005](ADR-0005-Planner-Capability.md) | Planner Capability | Accepted |
| [ADR-0006](ADR-0006-Runtime-Artifact-Ownership.md) | Runtime Artifact Ownership | Accepted |
| [ADR-0007](ADR-0007-Execution-Capability.md) | Execution Capability | Accepted |
| [ADR-0008](ADR-0008-Document-Parsing-Docling.md) | Document Parsing with Docling | Accepted |
| [ADR-0009](ADR-0009-Analysis-Canonical-Artifact.md) | Analysis Canonical Artifact | Accepted |
| [ADR-0010](ADR-0010-Hydra-Configuration.md) | Hydra Configuration | Accepted |
| [ADR-0011](ADR-0011-Pixi-Environment.md) | Pixi Environment | Accepted |
| [ADR-0012](ADR-0012-Experiment-Tracking-MLflow.md) | Experiment Tracking with MLflow | Accepted |
| [ADR-0013](ADR-0013-Research-Resource-Discovery.md) | Research Resource Discovery | Draft |
| [ADR-0014](ADR-0014-Execution-Planning-Capability.md) | Execution Planning Capability | Accepted |
| [ADR-0017](ADR-0017-Execution-Planning-Service-Architecture.md) | Execution Planning Service Architecture | Accepted |
| [ADR-0018](ADR-0018-Execution-Planning-Decision-Foundation.md) | Execution Planning Decision Foundation | Accepted |
| [ADR-0016](ADR-0016-GitHub-Discovery-Provider.md) | GitHub Discovery Provider | Draft |

## Platform Capability ADRs (v1.2)

These ADRs document the v1.2 platform capability layer. ADR-0014, ADR-0017, and ADR-0018 are **Accepted** (Execution Planning complete). ADR-0013 and ADR-0016 remain **Draft** until promoted at release tag.

| ADR | Capability | Canonical artifact |
|-----|------------|-------------------|
| [ADR-0013](ADR-0013-Research-Resource-Discovery.md) | Research Resource Discovery | `ResearchResourceDiscovery` |
| [ADR-0014](ADR-0014-Execution-Planning-Capability.md) | Execution Planning | `ExecutionStrategy` |
| [ADR-0017](ADR-0017-Execution-Planning-Service-Architecture.md) | Execution Planning service architecture | Workflow → Services → Ports → Providers → Builder |
| [ADR-0018](ADR-0018-Execution-Planning-Decision-Foundation.md) | Execution Planning Decision Foundation | ObservedFacts → Dimensions → Engineering Decisions |
| [ADR-0016](ADR-0016-GitHub-Discovery-Provider.md) | GitHub Discovery Provider | External evidence for Discovery (no clone) |

**Interface rule:** CLI and Python SDK delegate to `Man1Lab` (Platform Facade). Interfaces never call agents or orchestrators directly.

See [architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md), [architecture/EXECUTION_PLANNING.md](../architecture/EXECUTION_PLANNING.md), and [releases/v1.2.1.md](../releases/v1.2.1.md).

## Template

Use this template for new ADRs. Keep each ADR to one page.

```markdown
# ADR-NNNN — Title

## Status

Proposed | Accepted | Deprecated | Superseded by ADR-XXXX

## Date

YYYY-MM-DD

## Context

What problem or constraint led to this decision?

## Decision

What was decided?

## Alternatives

What other options were considered?

## Consequences

What are the positive and negative outcomes?
```

## Naming Convention

`ADR-NNNN-Short-Title.md`

- `NNNN` — four-digit sequential number
- `Short-Title` — hyphen-separated words

## Status Values

| Status | Meaning |
|--------|---------|
| Proposed | Under discussion, not yet adopted |
| Accepted | Active decision |
| Deprecated | No longer recommended, not yet replaced |
| Superseded | Replaced by another ADR |
