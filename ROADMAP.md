# Man1Lab Roadmap

**Last updated:** 2026-07-08  
**Current version:** v1.2.2 (Release Candidate)

For live implementation state see [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md). For release history see [docs/releases/README.md](docs/releases/README.md).

---

## Completed

### v1.0 — MVP (2026-06-29)

End-to-end single-paper reproduction prototype.

| Deliverable | Status |
|-------------|--------|
| Reader → Planner → Coder → Runner pipeline | ✅ |
| Verification · Review · Report | ✅ |
| Real LLM integration | ✅ |
| GQ-1 + Repository Acceptance Gate | ✅ |

Release: [release/v1.0.0.md](release/v1.0.0.md)

---

### v1.1 — Foundation (2026-06-30)

Platform infrastructure and canonical analysis artifact.

| Deliverable | Status |
|-------------|--------|
| `PaperReproductionAnalysis` canonical object | ✅ |
| Docling parsing ([ADR-0008](docs/adr/ADR-0008-Document-Parsing-Docling.md)) | ✅ |
| Hydra configuration ([ADR-0010](docs/adr/ADR-0010-Hydra-Configuration.md)) | ✅ |
| Pixi environment ([ADR-0011](docs/adr/ADR-0011-Pixi-Environment.md)) | ✅ |
| MLflow tracking ([ADR-0012](docs/adr/ADR-0012-Experiment-Tracking-MLflow.md)) | ✅ |
| Documentation governance | ✅ |

Release: [docs/releases/v1.1.0.md](docs/releases/v1.1.0.md)

---

### v1.2 — Platform Capability (2026-07-03 RC)

Unified platform interfaces and pre-implementation capabilities.

| Deliverable | Status |
|-------------|--------|
| Platform Facade (`Man1Lab`) | ✅ |
| CLI (`man1lab`) | ✅ |
| Python SDK (`pip install man1lab`) | ✅ |
| Package distribution (PEP 621) | ✅ |
| Lifecycle commands (`init`, `doctor`) | ✅ |
| Research Resource Discovery workflow | ✅ |
| GitHub Discovery Provider | ✅ |
| Execution Planning workflow | ✅ |
| Strategy-driven Planner integration | ✅ |
| Orchestrator: Analysis → Discovery → Execution Planning → Planner → … | ✅ |

Release: [docs/releases/v1.2.0.md](docs/releases/v1.2.0.md)

#### v1.2.1 — Execution Planning Stabilization (2026-07-08)

| Deliverable | Status |
|-------------|--------|
| Six embedded Execution Planning providers | ✅ |
| Decision Foundation | ✅ |
| Architecture stabilization | ✅ |

Release: [docs/releases/v1.2.1.md](docs/releases/v1.2.1.md)

#### v1.2.2 — LLM Platform & First-run Experience (2026-07-08 RC)

| Deliverable | Status |
|-------------|--------|
| LLM Provider foundation (`LLMManager`, `ProviderRegistry`) | ✅ |
| Model Registry + persistence | ✅ |
| OpenAI / DeepSeek / Anthropic providers | ✅ |
| `man1lab model` CLI (list, use, add, export, import, …) | ✅ |
| Interactive `man1lab init` first-model wizard | ✅ |
| Doctor LLM validation | ✅ |

Release: [docs/releases/v1.2.2.md](docs/releases/v1.2.2.md)

---

## Planned

### v1.3 — Repository Understanding

| Goal | Direction |
|------|-----------|
| Semantic repo structure mapping | Consume selected resources from `ResearchResourceDiscovery` |
| Align repo layout with analysis modules | Read-only — no code modification |
| Inform Execution Planning refinements | Downstream of committed strategy |

**Not started.** Architecture reserved in [ADR-0014](docs/adr/ADR-0014-Execution-Planning-Capability.md) Future Work.

---

### v1.4 — Repository Adaptation

| Goal | Direction |
|------|-----------|
| Patch / pin / fork discovered repos | Implementation layer concern |
| Align discovered code with paper requirements | After Repository Understanding |

**Not started.**

---

### v1.5 — Knowledge Memory

| Goal | Direction |
|------|-----------|
| Cross-run reproduction knowledge | Lineage atop canonical artifacts |
| Resource cache and rerun optimization | Discovery / platform concern |

**Not started.** Research phase only.

---

## Future Interfaces (not implemented)

| Interface | Status |
|-----------|--------|
| MCP server | Reserved — `interfaces/mcp/` layout |
| REST API | Reserved — `interfaces/api/` layout |

---

## Explicitly Out of Scope (v1.x)

- Autonomous research idea generation
- Multi-paper research programs
- Cloud-scale distributed execution
- Guaranteed SOTA benchmark reproduction
- Human-in-the-loop collaborative IDE

See [docs/architecture/ARCHITECTURE.md §9](docs/architecture/ARCHITECTURE.md).
