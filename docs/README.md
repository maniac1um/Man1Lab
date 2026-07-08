# Documentation Index

Navigation hub for Man1Lab v1.2.2 documentation.

**Principle:** Current documents answer *"What does the project do today?"* Historical reviews answer *"How did the project evolve?"*

---

## Start Here

| Document | Purpose |
|----------|---------|
| [GETTING_STARTED.md](GETTING_STARTED.md) | Install, init, doctor, reproduce; CLI and SDK workflow |
| [CURRENT_STATUS.md](CURRENT_STATUS.md) | **Single source of truth** — capabilities, pipeline, benchmarks, limitations |
| [CHANGELOG.md](../CHANGELOG.md) | Version history (v1.0.0 – v1.2.2) |
| [ROADMAP.md](../ROADMAP.md) | Completed milestones and planned work |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Research prototype — issues welcome, PRs not accepted |
| [releases/README.md](releases/README.md) | Release history |
| [releases/v1.2.2.md](releases/v1.2.2.md) | v1.2.2 LLM Platform & First-run Experience |
| [releases/v1.2.1.md](releases/v1.2.1.md) | v1.2.1 Execution Planning Stabilization |
| [releases/v1.2.0.md](releases/v1.2.0.md) | v1.2.0 Platform Capability Release notes |
| [releases/v1.1.0.md](releases/v1.1.0.md) | v1.1.0 Foundation Release notes |
| [release/v1.0.0.md](../release/v1.0.0.md) | v1.0.0 MVP release notes |
| [DEVELOPMENT.md](../DEVELOPMENT.md) | Engineering workflow, architecture freeze, commit policy |

---

## Architecture

| Document | Purpose |
|----------|---------|
| [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) | Platform architecture, interfaces, canonical artifacts |
| [architecture/infrastructure.md](architecture/infrastructure.md) | Infrastructure governance, adoption matrix, native vs external boundaries |
| [architecture/CAPABILITIES.md](architecture/CAPABILITIES.md) | Per-capability component reference (partial refresh for v1.1 detail) |

Root pointer: [ARCHITECTURE.md](../ARCHITECTURE.md)

---

## ADRs

Architecture Decision Records document significant design choices.

| Resource | Purpose |
|----------|---------|
| [adr/README.md](adr/README.md) | ADR index, template, platform capability overview |
| [ADR-0001](adr/ADR-0001-Workflow-Orchestrator.md) – [ADR-0012](adr/ADR-0012-Experiment-Tracking-MLflow.md) | Accepted infrastructure and pipeline decisions |
| [ADR-0013](adr/ADR-0013-Research-Resource-Discovery.md), [ADR-0014](adr/ADR-0014-Execution-Planning-Capability.md), [ADR-0016](adr/ADR-0016-GitHub-Discovery-Provider.md), [ADR-0017](adr/ADR-0017-Execution-Planning-Service-Architecture.md) | Platform capability ADRs (0013/0016 Draft; 0014/0017 Accepted) |

---

## Private work documents

Milestone reviews, audits, benchmarks, roadmaps, and adoption research live in **`private/`** (local, gitignored). See [reviews/README.md](reviews/README.md) for the migration pointer and [CONTRIBUTING.md § Documentation Policy](../CONTRIBUTING.md#documentation-policy).

| Category | Local path |
|----------|------------|
| Roadmaps | `private/roadmap/` |
| Benchmarks | `private/benchmark/` |
| Audits | `private/audit/` |

---

## API

| Resource | Purpose |
|----------|---------|
| [api/README.md](api/README.md) | Public API contract summary (facade methods; may lag CLI) |

---

## Project Root

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Project homepage — CLI, SDK, quick start |

---

## Documentation Classification

Man1Lab separates **public documentation** (committed to GitHub) from **private documentation** (local `private/`, gitignored).

### Public documentation (GitHub)

Formal decisions and maintained project docs:

```text
docs/
├── architecture/     → Platform design (ARCHITECTURE.md, infrastructure.md)
├── adr/              → Accepted architecture decisions (ADR)
├── api/              → Public API contracts
├── GETTING_STARTED.md
├── CURRENT_STATUS.md
└── releases/           → Release notes
ROADMAP.md              → Roadmap (root)
```

**Principle:** GitHub stores **final decisions** and **formal documentation** only.

### Private documentation (local only)

Research process, audits, benchmarks, and drafts — **not** in Git:

```text
private/
├── adoption-review/  → Technology Adoption Reviews (Docling, MLflow, …)
├── audit/            → Architecture audit reports
├── benchmark/          → Benchmark run reports
├── design/
│   ├── drafts/       → Draft designs
│   ├── migrations/   → Phase migration reports
│   ├── future/       → Future architecture explorations
│   └── experiments/  → Experimental design spikes
├── meeting/          → Meeting notes
├── notes/            → Research notes
├── roadmap/          → Working roadmap drafts
└── scratch/          → Temporary scratch
```

**Principle:** Reviews inform ADRs; ADRs record accepted decisions. Do not treat a Technology Review as a substitute for an ADR.

Full policy: [CONTRIBUTING.md](../CONTRIBUTING.md#documentation-policy)
