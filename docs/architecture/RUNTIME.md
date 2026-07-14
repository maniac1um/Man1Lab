# Runtime Architecture

**Project:** Man1Lab  
**Status:** Canonical architecture specification  
**Audience:** Architects, contributors, and long-term maintainers  
**Horizon:** 3–5 years  
**Last updated:** 2026-07-13

This document specifies the **Platform Runtime** subsystem — process-level infrastructure that supports all Man1Lab interfaces and business capabilities.

**Naming note:** Man1Lab also uses *runtime* in the **Execution Layer** sense (training scripts, environments, `ExecutionResult`). This document refers exclusively to the **Platform Runtime** — the subsystem that owns process lifecycle, infrastructure resources, profiling, and user session lifetime. See [ARCHITECTURE.md](ARCHITECTURE.md) for the reproduction pipeline.

For implementation phase audits, see [reviews/8.1_runtime_performance_audit/](../reviews/8.1_runtime_performance_audit/) through [reviews/8.5_runtime_session/](../reviews/8.5_runtime_session/).

---

## 1. Overview

### What Runtime Is

The **Runtime** subsystem is the **process-level infrastructure** of Man1Lab. It sits between the Platform Facade and business workflows, providing a stable ownership model for how the platform boots, holds shared infrastructure, observes itself, and scopes user interaction.

Runtime answers: *How does the Man1Lab process come into existence, hold shared resources, and shut down cleanly — without coupling business logic to process concerns?*

Runtime is a **first-class architecture** alongside Analysis, Discovery, and Execution Planning. It is not a feature of any single capability; it is the substrate on which all capabilities execute.

### What Runtime Owns

| Concern | Description |
|---------|-------------|
| **Process lifecycle** | Platform boot, readiness, and shutdown |
| **Runtime resources** | Registration, resolution, health, and cache policy metadata for shared infrastructure |
| **Lazy initialization** | Deferred creation of expensive infrastructure until first access |
| **Profiling** | Startup and infrastructure observation — timelines, measurements, reports |
| **Session lifecycle** | User interaction lifetime distinct from process lifetime |
| **Execution persistence** | Workspace-scoped durable execution state through a dedicated `ExecutionStore` (Phase 1–2 implemented) |

### What Runtime Does NOT Own

| Concern | Correct owner |
|---------|---------------|
| Paper analysis | Analysis layer |
| External resource discovery | Discovery layer |
| Engineering strategy | Execution Planning layer |
| Task decomposition | Planner |
| Code generation | Implementation (Coder) |
| Training script execution | Execution (Runner) |
| Engineering decisions | Business capabilities and agents |
| Workflow orchestration | Workflow coordinator |
| Agent logic | Individual agents |

Runtime provides **infrastructure and lifetime boundaries**. It does not interpret papers, rank repositories, commit strategies, or generate code.

### Why Runtime Exists

Before Runtime was introduced, infrastructure concerns (configuration loading, LLM manager creation, startup measurement) were embedded in the composition root without explicit ownership. That made it difficult to:

- Reason about process lifetime vs user interaction lifetime
- Defer expensive initialization safely
- Observe startup cost without instrumenting business workflows
- Support future interfaces (interactive console, daemon, MCP, REST) on a shared foundation

Runtime was introduced to **separate process infrastructure from business capabilities** — mirroring how Discovery and Execution Planning separate pre-implementation concerns from implementation.

---

## 2. Design Principles

| Principle | Meaning |
|-----------|---------|
| **Ownership Before Access** | Every shared infrastructure object has a declared owner in the Runtime hierarchy. Business modules request resources through the facade; they do not construct infrastructure directly. |
| **Infrastructure Before Business** | Runtime boots and becomes ready before business workflows execute. Business logic never drives process lifecycle. |
| **Observe Before Optimize** | Profiling and resource health exist before performance optimization. Measurement is a first-class Runtime concern, not an afterthought in workflows. |
| **Initialize on Demand** | Expensive infrastructure is created lazily at first access unless startup policy requires earlier resolution. Runtime owns the deferral policy. |
| **One Runtime, Multiple Interfaces** | CLI, Interactive Console, SDK, and future MCP and REST share one `PlatformRuntime` per process. Interfaces delegate to the facade; the facade delegates lifecycle to Runtime. |
| **Business Unawareness** | Workflow, agents, Discovery, and Execution Planning do not import Runtime internals. Dependency flows downward: interfaces → facade → runtime → business. |
| **Stable Substrate, Evolving Wiring** | Runtime core defines lifecycle, ownership, and observation contracts. Application-layer wiring may evolve (new resource types) without changing business capability boundaries. |

---

## 3. High-Level Architecture

```text
Interfaces
    CLI  ·  Interactive Console  ·  SDK  ·  REST (future)  ·  MCP (future)
                              ↓
                    Platform Facade (Man1Lab)
                              ↓
                    PlatformRuntime
                    ├── RuntimeContext
                    │     ├── RuntimeResourceManager
                    │     ├── WorkspaceArtifactStore
                    │     └── ExecutionStore ✅
                    ├── RuntimeSession
                    │     └── SessionWorkspace
                    └── RuntimeProfiler (per observation run)
                              ↓
                    Business Workflows
                    Analysis → Discovery → Execution Planning
                              ↓
                    Planner → Implementation → Execution → …
```

### Layer responsibilities

| Layer | Responsibility |
|-------|----------------|
| **Interfaces** | User-facing entry points. Translate commands into facade calls. Never own process lifecycle or infrastructure. |
| **Platform Facade** | Single public composition root. Delegates lifecycle, session, and resource access to Runtime. Wires business workflows when reproduction runs. |
| **PlatformRuntime** | Process lifetime owner. Coordinates boot, readiness, shutdown, context, session, and profiling orchestration. |
| **RuntimeContext** | Container for the resource manager and runtime-scoped slots. The unit of “what this process holds.” |
| **RuntimeResourceManager** | Registers, resolves, and describes infrastructure resources. Exposes health and cache policy metadata. |
| **RuntimeSession** | User interaction lifetime. Holds in-memory workspace placeholders for the current interaction scope. |
| **RuntimeProfiler** | Captures hierarchical timing for observation runs. Independent of business workflow stages. |
| **ExecutionStore** | Runtime-owned durable adapter for execution runs, task attempts, traces, artifact manifests, and reports. It does not schedule tasks. |
| **Business workflows** | Domain capabilities scheduled by the workflow coordinator. Unaware of Runtime internals. |

### Dependency direction

```text
interfaces  →  application (facade, wiring)  →  runtime core
runtime core  →  stdlib and runtime packages only
business capabilities  ↛  runtime internals
```

Application-layer modules may register resource factories into Runtime. Runtime core does not import agents, workflows, or providers.

---

## 4. Runtime Lifecycle

### PlatformRuntime

`PlatformRuntime` is the **process lifetime owner**. One instance typically exists per Man1Lab process, created when the Platform Facade initializes.

| Operation | Purpose |
|-----------|---------|
| **Startup** | Transition from uninitialized to ready; create context and session shell |
| **Shutdown** | Graceful teardown; close active session; release context |
| **Readiness check** | Whether business operations may proceed |

The facade triggers startup when constructed with a new runtime. Shutdown is explicit — suitable for tests, embedded use, and future daemon modes.

### Lifecycle state machine

```text
NEW
  ↓
BOOTSTRAPPING
  ↓
READY
  ↓
SHUTTING_DOWN
  ↓
STOPPED
```

| State | Meaning |
|-------|---------|
| **NEW** | Runtime exists but has not started. Initial state. |
| **BOOTSTRAPPING** | Startup in progress. Context and session are being established. |
| **READY** | Process is ready. Business operations and resource resolution may proceed. |
| **SHUTTING_DOWN** | Teardown in progress. New work should not start. |
| **STOPPED** | Terminal state. Context and session references cleared. |

### Transition philosophy

- **Deterministic transitions** — only defined state changes are permitted. Invalid transitions are rejected rather than silently ignored.
- **Fail-safe boot** — startup failure moves to **STOPPED** rather than leaving the runtime in a partially initialized state.
- **Explicit shutdown** — only **READY** may enter **SHUTTING_DOWN**. Shutdown closes an active session before releasing context.
- **No resurrection** — **STOPPED** is terminal for a given instance. A new process requires a new runtime instance.

Runtime lifecycle is **orthogonal** to workflow execution. A reproduction run does not change platform lifecycle state.

---

## 5. Runtime Context

### Purpose

`RuntimeContext` is the **ownership container** for everything the process holds at the infrastructure level. It exists so that resource management, lazy initialization, and future workspace slots have a single parent — without scattering ownership across the facade or business modules.

### What RuntimeContext owns

| Owned concern | Role |
|---------------|------|
| **RuntimeResourceManager** | Registry and resolver for infrastructure resources |
| **Resource status projection** | Summaries used by profiling reports |
| **Session reference** | Link to the active `RuntimeSession` for this process |
| **Future workspace slot** | Reserved for persistent workspace ownership (not yet active) |

### What RuntimeContext does not own

- Business artifacts (`PaperReproductionAnalysis`, `ExecutionStrategy`, etc.)
- Workflow history or experiment tracking runs
- Agent instances (constructed by facade wiring, not stored as runtime resources today)

### Why RuntimeContext exists

Without a context object, the facade would accumulate infrastructure fields indefinitely. `RuntimeContext` provides a **stable boundary** between “what the process holds” and “what the facade exposes publicly.” As new infrastructure types appear (caching layers, connection pools, future daemon handles), they attach to context — not to business capabilities.

---

## 6. Runtime Resource Management

### Components

| Concept | Role |
|---------|------|
| **RuntimeResourceManager** | Register factories, resolve resources, aggregate descriptors and statistics |
| **RuntimeResourceDescriptor** | Immutable metadata for a registered resource (name, type, cache policy) |
| **RuntimeResourceHealth** | Lifecycle health of a resource: deferred, initializing, ready, or failed |
| **CachePolicy** | Declared cache semantics (runtime-scoped, session-scoped, or never) — metadata today, eviction algorithms future |

### Ownership model

1. **Registration** — application wiring registers named resources with factories and metadata at startup.
2. **Resolution** — consumers request resources by key through the manager. First access triggers lazy initialization.
3. **Observation** — descriptors and health feed profiling reports. Business modules do not inspect health directly.
4. **Failure** — a failed initialization is recorded; subsequent access surfaces the failure consistently.

### Current resource categories

Infrastructure resources owned by Runtime today include, among others:

| Category | Examples |
|----------|----------|
| **Configuration** | Application settings resolved from Hydra and environment |
| **Prompt infrastructure** | Prompt registry / loader |
| **LLM platform** | Provider registry, LLM manager |

Business workflows, agents, Discovery providers, and Execution Planning services are **not** runtime-owned resources. They are constructed by application wiring when reproduction runs.

### Why resource metadata exists

Descriptors and health states make infrastructure **observable** without coupling business logic to initialization order. Profiling reports can answer “what is ready vs deferred?” at startup — a prerequisite for future optimization and interactive interfaces.

`CachePolicy` is intentionally metadata-first: all current wired resources use runtime-scoped caching. Session and never-cache policies are reserved for future session-bound and stateless resources.

---

## 7. Lazy Initialization

### Model

Runtime owns **when** infrastructure is created, not **what** business decisions are made. Resources register a factory; the manager wraps factories in a lazy initialization primitive that guarantees:

- **Initialize once** per process (for runtime-scoped resources)
- **Thread-safe** first access
- **Visible state** — deferred until accessed, then initializing, then ready or failed

### Why Runtime owns initialization

| Without Runtime ownership | With Runtime ownership |
|---------------------------|------------------------|
| Facade constructor eagerly loads all infrastructure | Facade triggers startup; resources resolve on demand |
| Business modules import configuration loaders directly | Business modules receive already-wired dependencies from facade |
| Startup cost is opaque | Profiling reports deferred vs ready resources |
| New interfaces duplicate boot logic | All interfaces share one lazy resolution path |

### Deferred initialization philosophy

**Defer by default** for expensive infrastructure. Resolve configuration early when required for wiring decisions; defer LLM manager and prompt registry until first use unless startup policy requires otherwise.

Lazy initialization is an **implementation strategy** behind the resource manager. Business capabilities remain unaware of whether a dependency was eager or lazy.

---

## 8. Runtime Profiling

### Purpose

Profiling belongs to **Runtime**, not to business workflows. Startup cost, infrastructure readiness, and session metadata are process concerns — measuring them inside Analysis or Discovery would violate layer boundaries.

### Architecture

| Component | Role |
|-----------|------|
| **RuntimeProfiler** | Hierarchical stage timer for an observation run |
| **Timeline** | Ordered collection of stage measurements |
| **Measurements** | Nested stage records with durations |
| **Report** | Formatted output combining stages, resource status, and session info |

### Observation model

- Each profiling run uses a **new profiler instance** — no global singleton.
- Stages nest hierarchically (e.g., startup phases containing sub-steps).
- Reports include **wall-clock total** plus per-stage breakdown.
- Resource lines reflect descriptor health and cache policy (e.g., ready vs deferred).
- Session section reflects interaction state when relevant.

### Startup profiling

Application-layer startup profiling measures platform bring-up phases (import, configuration, facade, workflow probe) without executing a full reproduction. This is exposed through the facade and CLI (`man1lab profile`) as an **observation command**, not a business operation.

### Boundary

Business workflow stages (Reader, Discovery, Planner, etc.) are **not** instrumented through Runtime profiling APIs today. Future cross-cutting observability may extend Runtime reports without moving profiling into capability workflows.

---

## 9. Runtime Session

### Purpose

`RuntimeSession` models **user interaction lifetime** — distinct from **process lifetime**.

| Lifetime | Owner | Scope |
|----------|-------|-------|
| **Process lifetime** | `PlatformRuntime` | From startup to shutdown |
| **User interaction lifetime** | `RuntimeSession` | From session open to session close |

A single process may serve multiple sequential sessions over its life (future interactive modes). Today, one session shell is created at startup and opened explicitly when interaction begins.

### Session state machine

```text
NEW
  ↓
ACTIVE
  ↓
CLOSED
```

| State | Meaning |
|-------|---------|
| **NEW** | Session exists but no interaction is active |
| **ACTIVE** | User interaction scope is open |
| **CLOSED** | Session terminal; no further interaction on this instance |

### SessionWorkspace

`SessionWorkspace` holds **session-scoped references** for the current interaction:

- Workspace root path
- Current paper reference
- Cached handles to analysis, discovery, and strategy artifacts

As of v1.2.4, successful console stages also persist canonical artifacts via `WorkspaceArtifactStore` (runtime-owned):

```text
{workspace_root}/analysis/     → analysis.json, analysis.md
{workspace_root}/discovery/    → resources.json, summary.md
{workspace_root}/planning/     → execution_strategy.json, summary.md
{workspace_root}/decision/     → decision_trace.json, decision_trace.md,
                                 execution_graph.json, execution_graph.md
```

`hydrate_workspace_from_disk()` loads persisted artifacts when session references are absent. Diagnostics recommend the next command when required artifacts are missing.

Session references remain in-memory for the interaction scope. On-disk artifacts enable resume across sessions without replacing experiment tracking or workflow history.

### Facade delegation

The Platform Facade exposes session status and close operations by delegating to `PlatformRuntime`. Interfaces do not manipulate session state directly.

### Why sessions matter for future interfaces

Interactive console, GUI, and long-lived daemon modes require a scope narrower than the process. Session separates “the platform is running” from “the user is in an active interaction” — enabling conversation context, workspace pinning, and per-session resource policy in future phases without redesigning process lifecycle.

---

## 10. Runtime Ownership Model

### Hierarchy

```text
PlatformRuntime                 ← process lifetime
    ↓
RuntimeContext                  ← infrastructure container
    ↓
RuntimeResourceManager          ← resource registry and resolution
    ↓
Lazy Resources                  ← configuration, prompts, LLM platform, …
    ↓
Business Modules                ← agents, workflows (wired by facade, not runtime-owned)
```

Parallel branch:

```text
PlatformRuntime
    ↓
RuntimeSession                  ← interaction lifetime
    ↓
SessionWorkspace                ← interaction references + hydration
    ↓
WorkspaceArtifactStore          ← runtime-owned stage persistence
```

Execution persistence branch (implemented in v1.3.0):

```text
PlatformRuntime
    ↓
RuntimeContext                  ← owns/provides durable infrastructure
    ↓
ExecutionStore                  ← workspace-scoped persistence adapter
    ↑ injected by application composition
ExecutionEngine                 ← owns state semantics and scheduling
```

`ExecutionStore` is separate from `WorkspaceArtifactStore`. The latter persists low-frequency Analysis, Discovery, Planning, and Decision snapshots; the former persists a live execution state machine with task attempts, append-only trace events, artifact manifests, and crash recovery metadata. A session may reference a run ID but never owns the run.

### Dependency rules

| Rule | Rationale |
|------|-----------|
| Runtime → business forbidden | Runtime core must not depend on agents or workflows |
| Business → runtime internals forbidden | Capabilities stay testable without process infrastructure |
| Facade mediates all access | Single public entry preserves interface stability |
| Wiring lives in application layer | Factories may import configuration and providers; runtime core stays pure |
| Runtime owns storage; Execution owns semantics | Runtime supplies the concrete store through an Execution-defined port and never schedules or reconciles tasks |
| Profiling is orthogonal | Observation does not participate in lifecycle transitions |

### Composition flow (conceptual)

1. Interface invokes facade.
2. Facade ensures runtime is **READY**.
3. Facade resolves infrastructure through context resources.
4. Facade constructs or delegates to business workflows.
5. Business workflows consume canonical artifacts — not runtime state machines.

---

## 11. Current Limitations

Honest constraints as of v1.2.3 (phases 8.1–8.6):

| Limitation | Notes |
|------------|-------|
| **No persistent session workspace** | Resolved in v1.2.4 — `WorkspaceArtifactStore` persists stage artifacts; session holds references |
| **No conversation memory** | Console does not retain dialogue history |
| **No daemon mode** | Process lifetime follows facade / CLI invocation |
| **No distributed runtime** | Single-process ownership model |
| **Cache policy is metadata only** | No eviction algorithms; runtime-scoped cache dominates |
| **Business workflows not runtime-owned** | Orchestrator and agents wired outside resource manager |
| **No business-stage profiling** | Runtime profiles infrastructure startup, not full reproduction pipeline |
| **No persistent profiling storage** | Reports are ephemeral per run |
| **Session not auto-opened on CLI subcommands** | Subcommands use one-shot facade calls; console opens session on start |
| **Workspace slot on context unused** | Reserved; not yet migrated from legacy paths |
| **No durable ExecutionStore** | Resolved in v1.3 Phase 1–2 — `FileExecutionStore` with journal-plus-snapshot durability |

These limitations are **intentional scope boundaries** for the foundation phases, not architectural oversights.

---

## 12. Future Evolution

Runtime was designed to support progressive enhancement without restructuring business capabilities.

### Completed foundation (phases 8.1–8.6)

```text
8.1 Profiling
  ↓
8.2 Lifecycle
  ↓
8.3 Lazy Initialization
  ↓
8.4 Resource Management
  ↓
8.5 Runtime Session
  ↓
8.5.1 Runtime Integration
  ↓
8.6 Interactive Console
```

| Phase | Deliverable |
|-------|-------------|
| **8.1** | Profiling subsystem, startup observation, CLI profile command |
| **8.2** | `PlatformRuntime`, lifecycle state machine, `RuntimeContext` |
| **8.3** | Lazy initialization primitives, deferred resource resolution |
| **8.4** | Resource manager, descriptors, health, cache policy metadata |
| **8.5** | Session lifecycle, `SessionWorkspace` placeholders |
| **8.5.1** | `RuntimeInfrastructure`; agents receive injected dependencies |
| **8.6** | `Man1LabConsole` — `man1lab` with no args |

### Planned interfaces and modes

Before additional interfaces, v1.3 introduces Runtime-owned execution persistence in this order: dedicated `ExecutionStore`, Runtime/Application injection, LocalExecutor, console facade integration, then an end-to-end crash/resume reproduction. See [EXECUTION_RUNTIME.md](EXECUTION_RUNTIME.md).

```text
Future: Daemon
Future: REST
Future: MCP
Future: GUI
```

| Direction | Runtime role |
|-----------|--------------|
| **Daemon** | Long-lived **READY** process; session multiplexing |
| **REST / MCP** | Remote interfaces share one runtime per server process |
| **GUI** | Session and workspace as UI binding targets |

### Evolution principles

- **Extend Runtime, don’t embed in business** — new interfaces attach to facade and runtime, not to agents.
- **Metadata before mechanism** — cache policy, health, and descriptors precede eviction and persistence implementations.
- **Session before persistence** — interaction lifetime is modeled before disk-backed workspace storage.
- **Observe before optimize** — profiling data informs startup and resource policy changes.

---

## Related Documents

| Document | Relationship |
|----------|--------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Platform pipeline and capability layers |
| [EXECUTION_RUNTIME.md](EXECUTION_RUNTIME.md) | Runtime-owned execution persistence, crash recovery, and resume boundaries |
| [infrastructure.md](infrastructure.md) | External tool adoption (Hydra, Pixi, MLflow) |
| [CURRENT_STATUS.md](../CURRENT_STATUS.md) | Live implementation status |
| [reviews/8.1_runtime_performance_audit/](../reviews/8.1_runtime_performance_audit/) | Profiling phase audit |
| [reviews/8.2_runtime_lifecycle/](../reviews/8.2_runtime_lifecycle/) | Lifecycle phase audit |
| [reviews/8.3_runtime_lazy_initialization/](../reviews/8.3_runtime_lazy_initialization/) | Lazy initialization phase audit |
| [reviews/8.4_runtime_resource_management/](../reviews/8.4_runtime_resource_management/) | Resource management phase audit |
| [reviews/8.5_runtime_session/](../reviews/8.5_runtime_session/) | Session phase audit |
| [reviews/8.5.1_runtime_integration/](../reviews/8.5.1_runtime_integration/) | Runtime integration audit |
| [reviews/8.6_man1lab_console/](../reviews/8.6_man1lab_console/) | Interactive console audit |

---

**Last aligned with:** Man1Lab v1.3 Execution Runtime Integration implementation
