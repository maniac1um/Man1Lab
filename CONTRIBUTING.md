# Contributing

Man1Lab is an **active research prototype** for academic demonstration of autonomous paper reproduction. It is maintained as a single-author research project, not as a community-driven open-source program.

## Issues

Bug reports, reproduction failures, and documentation feedback are welcome via GitHub Issues. Please include:

- Python version and OS
- Whether you used mock or real LLM providers
- Relevant log excerpts from `logs/` or `outputs/`

## Pull Requests

**Pull requests are not currently accepted.**

The codebase, architecture, and milestone plan are managed by the maintainer. External contributions may be reconsidered if the project transitions beyond the research-prototype stage.

## Architectural Changes

Architecture, workflow design, frozen interfaces, and capability scope are **maintainer-managed**. See [docs/adr/README.md](docs/adr/README.md) for accepted decisions and [DEVELOPMENT.md](DEVELOPMENT.md) for the internal engineering workflow.

## Reading the Codebase

| Document | Purpose |
|----------|---------|
| [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) | Install via pip or Pixi; `man1lab init`, `doctor`, `reproduce` |
| [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) | Current capabilities and limitations |
| [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) | Platform architecture and canonical artifacts |
| [ROADMAP.md](ROADMAP.md) | Completed and planned milestones |
| [docs/reviews/README.md](docs/reviews/README.md) | Pointer to private work documents (migrated) |

---

## Documentation Policy

Man1Lab maintains two documentation layers: **public** (version-controlled on GitHub) and **private** (local only, not committed).

### Public documentation (in Git)

These documents describe **accepted decisions** and **formal project documentation**. They belong under `docs/`, `release/`, or project root guides:

| Category | Location | Examples |
|----------|----------|----------|
| Architecture Decision Records | `docs/adr/` | ADR-0001 – ADR-0016 |
| Architecture | `docs/architecture/` | `ARCHITECTURE.md`, `infrastructure.md` |
| API documentation | `docs/api/` | Public agent contracts |
| User / developer guides | `docs/`, root | `GETTING_STARTED.md`, `DEVELOPMENT.md` |
| Release notes | `docs/releases/`, `release/` | Version release documents |
| Current status | `docs/CURRENT_STATUS.md` | Capabilities and limitations |

**Rule:** If a document records a **final architecture decision**, it becomes an **ADR** (or updates an existing ADR). ADRs are the durable audit trail.

### Private documentation (local only)

Research and design **process** documents stay in `private/` at the repository root. This directory is listed in `.gitignore` and **must not be committed**:

| Category | Suggested path under `private/` |
|----------|----------------------------------|
| Technology Adoption Reviews | `private/adoption-review/` |
| Architecture audits | `private/audit/` |
| Benchmark reports | `private/benchmark/` |
| Draft / future / experimental designs | `private/design/drafts/`, `future/`, `experiments/` |
| Migration reports (development record) | `private/design/migrations/` |
| Meeting notes | `private/meeting/` |
| Research notes | `private/notes/` |
| Roadmaps (working drafts) | `private/roadmap/` |
| Scratch / temporary | `private/scratch/` |

**Rule:** Technology Adoption Reviews and audit reports are **research inputs**. They inform ADRs but **do not replace ADRs**. When a decision is accepted, record it in `docs/adr/` and keep the review local (or remove from public `docs/reviews/` after migration).

### Classification summary

```text
Technology Review  →  research process  →  private/adoption-review/
ADR                →  final decision    →  docs/adr/
Architecture doc   →  formal design     →  docs/architecture/
Migration report   →  process (legacy)   →  migrate to private/ when closing phase
```

See [docs/README.md](docs/README.md#documentation-classification) for the public documentation index.
