# Review Documents (Migrated)

Historical milestone reviews, integration reports, technology adoption reviews, and audit documents have been **migrated to the local private documentation layer** per [Documentation Policy](../../CONTRIBUTING.md#documentation-policy).

They are **not** stored in this public repository.

## Where to find migrated documents

| Category | Local path (gitignored) |
|----------|-------------------------|
| Technology Adoption Reviews | `private/adoption-review/` |
| Architecture audits | `private/audit/` |
| Benchmark reports | `private/benchmark/` |
| Migration reports | `private/design/migrations/` |
| Milestone design drafts | `private/design/drafts/milestones/` |
| Working roadmaps | `private/roadmap/` |
| Research notes | `private/notes/` |

## Public references

| Need | Document |
|------|----------|
| Current capabilities and benchmarks (summary) | [CURRENT_STATUS.md](../CURRENT_STATUS.md) |
| Accepted architecture decisions | [adr/README.md](../adr/README.md) |
| Platform architecture | [architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md) |
| Infrastructure adoption | [architecture/infrastructure.md](../architecture/infrastructure.md) |

**Rule:** Technology reviews inform ADRs; ADRs are the durable public record. Do not commit files under `private/` to Git.
