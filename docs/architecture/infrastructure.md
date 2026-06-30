# Man1Lab Infrastructure Governance

**Version:** v1.1.0  
**Status:** Living document — infrastructure adoption and boundaries  
**Audience:** Maintainers, contributors, and architecture reviewers  
**Horizon:** 3–5 years

This document governs **how Man1Lab adopts external tools** without letting infrastructure concerns leak into the research reproduction pipeline. It complements [ARCHITECTURE.md](ARCHITECTURE.md) (platform layers) and [ADR index](../adr/README.md) (specific decisions).

For platform vision and layer boundaries, see ARCHITECTURE.md. For individual tool rationale, see the ADRs referenced below.

---

## Purpose

Man1Lab integrates mature external infrastructure (configuration, environment management, parsing libraries, LLM SDKs) while preserving:

- **Clear ownership** — what is Man1Lab-native vs external
- **Thin boundaries** — business layers do not import infrastructure frameworks
- **Traceable decisions** — every significant adoption recorded in an ADR
- **Long-term replaceability** — ports and adapters allow swapping backends

Infrastructure governance prevents the platform from becoming a monolith tied to any single vendor tool while also preventing unnecessary reimplementation of solved problems.

---

## Infrastructure Principles

| Principle | Meaning |
|-----------|---------|
| **Thin integration** | External tools wrap behind ports, facades, or repo-root entrypoints. One integration layer; no deep embedding in agents. |
| **Ports & adapters** | Business code depends on abstractions (`SettingsProvider`, `DocumentParser`, `LLMProvider`). Concrete tools live in adapters or infrastructure modules. |
| **Technology Adoption Review** | New infrastructure requires explicit review: problem statement, alternatives, boundary impact, ADR before merge. |
| **ADR required** | Significant adoptions (configuration framework, environment manager, parsing backend) must have an ADR. See [adr/README.md](../adr/README.md). |
| **Avoid reinventing wheels** | Prefer established tools for config, env, and parsing when Man1Lab adds no unique value rebuilding them. |
| **Native vs external boundary** | Man1Lab-native: domain model, agents, workflow, validation, reproduction logic. External: Hydra, Pixi, Docling library, cloud LLM APIs. |
| **Business layer ignorance** | Agents and workflow must not import Hydra, Pixi, or other repo infrastructure directly. |
| **Two environment contexts** | **Developer environment** (Pixi at repo root) ≠ **reproduction workspace environment** (venv inside generated projects). Do not conflate them. |

---

## Current Infrastructure Stack

```text
┌─────────────────────────────────────────────────────────────┐
│  EXTERNAL — Repository Infrastructure (developer machine)    │
│  Pixi (pixi.toml) → Python 3.12 + locked dependencies        │
│  Hydra (conf/) → composed application settings               │
│  MLflow (tracking/) → experiment runs via ExperimentTracker  │
│  Legacy: requirements.txt + pip (compatibility)              │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  MAN1LAB NATIVE — Application & Platform Layers              │
│  Workflow orchestrator → Agents → Domain artifacts           │
│  Configuration port (SettingsProvider) + config facade       │
│  Parsing port (DocumentParser) → Docling / PyMuPDF adapters    │
│  Tracking port (ExperimentTracker) → MLflow / noop adapters  │
│  LLM port (LLMProvider) → OpenAI / Anthropic adapters        │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  EXTERNAL — Reproduction Workspace Runtime (per paper)       │
│  EnvironmentService: .venv + pip inside generated Workspace  │
│  (Not Pixi — Execution layer concern)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Adoption Matrix

### Foundation infrastructure summary

| Capability | Tool | Status |
|------------|------|--------|
| Paper Parsing | Docling (+ PyMuPDF fallback) | **Adopted** |
| Configuration | Hydra | **Adopted** |
| Environment | Pixi | **Adopted** |
| Experiment Tracking | MLflow | **Adopted** |
| Dataset Versioning | DVC | Pending |
| Workflow Engine | TBD | Research |

### Detailed matrix

| Capability | Tool | Status | ADR | Owner |
|------------|------|--------|-----|-------|
| **Platform domain model** | `PaperReproductionAnalysis` | Adopted | [ADR-0009](../adr/ADR-0009-Analysis-Canonical-Artifact.md) | Man1Lab Native |
| **Workflow scheduling** | Workflow orchestrator | Adopted | [ADR-0001](../adr/ADR-0001-Workflow-Orchestrator.md) | Man1Lab Native |
| **Prompt loading** | Prompt infrastructure | Adopted | [ADR-0003](../adr/ADR-0003-Prompt-Infrastructure.md) | Man1Lab Native |
| **Document parsing (default)** | Docling | Adopted | [ADR-0008](../adr/ADR-0008-Document-Parsing-Docling.md) | External (via Native adapter) |
| **Document parsing (fallback)** | PyMuPDF | Adopted | [ADR-0008](../adr/ADR-0008-Document-Parsing-Docling.md) | External (via Native adapter) |
| **Configuration composition** | Hydra | Adopted | [ADR-0010](../adr/ADR-0010-Hydra-Configuration.md) | External Infrastructure |
| **Configuration access port** | `SettingsProvider` | Adopted | [ADR-0010](../adr/ADR-0010-Hydra-Configuration.md) | Man1Lab Native |
| **Legacy config facade** | `config.py` module projection | Retained — Phase 1 shim | [ADR-0010](../adr/ADR-0010-Hydra-Configuration.md) | Man1Lab Native |
| **Developer environment** | Pixi | Adopted | [ADR-0011](../adr/ADR-0011-Pixi-Environment.md) | External Infrastructure |
| **Legacy pip install** | `requirements.txt` | Retained — compatibility | [ADR-0011](../adr/ADR-0011-Pixi-Environment.md) | External Infrastructure |
| **Experiment tracking** | MLflow | Adopted | [ADR-0012](../adr/ADR-0012-Experiment-Tracking-MLflow.md) | External (via Native adapter) |
| **Tracking access port** | `ExperimentTracker` | Adopted | [ADR-0012](../adr/ADR-0012-Experiment-Tracking-MLflow.md) | Man1Lab Native |
| **Dataset versioning** | DVC | Pending | — | — |
| **Workflow engine (external)** | TBD | Research | — | — |
| **LLM inference** | OpenAI / Anthropic APIs | Adopted | — | External Infrastructure |
| **Reproduction workspace venv** | pip + `EnvironmentService` | Adopted | [ADR-0006](../adr/ADR-0006-Runtime-Artifact-Ownership.md), [ADR-0007](../adr/ADR-0007-Execution-Capability.md) | Man1Lab Native (Execution layer) |
| **CI / automation** | — | Not adopted | — | Pending |
| **Lint / format** | — | Not adopted | — | Pending |

### Owner definitions

| Owner | Meaning |
|-------|---------|
| **Man1Lab Native** | Designed, owned, and evolved by Man1Lab. Defines platform behavior and contracts. |
| **External Infrastructure** | Third-party tool or service. Integrated thinly; replaceable via ADR-reviewed migration. |
| **External (via Native adapter)** | Third-party library hidden behind a Man1Lab port. Business layers see the port, not the library. |

---

## Pending Research

Items under evaluation or deferred to a future phase. **No adoption without ADR.**

| Topic | Question | Likely owner |
|-------|----------|--------------|
| **Hydra Phase 2** | Migrate remaining `import config` call sites to `SettingsProvider`; retire facade | Man1Lab Native |
| **Pixi Phase 2** | Remove `requirements.txt`; CI via `setup-pixi` | External Infrastructure |
| **Hydra CLI overrides** | Native `python app.py parser.backend=pymupdf` without custom parsing | External Infrastructure |
| **CI platform** | GitHub Actions vs alternatives | External Infrastructure |
| **Lint / format** | ruff, black, or equivalent + Pixi tasks | External Infrastructure |
| **Lockfile sync** | Generate `requirements.txt` from Pixi lock vs manual dual maintenance | Governance process |
| **Repository Discovery tooling** | Search/index infrastructure for official repos | External (future ADR) |
| **Cloud execution** | Remote runners, containers | External (future ADR) |

---

## Governance Rules

### 1. Adoption process

1. **Problem** — State the infrastructure gap in platform terms (not tool-first).
2. **Alternatives** — Evaluate at least one alternative, including "build native."
3. **Boundary impact** — Confirm which layers may import the tool (usually: none among agents).
4. **ADR** — Write ADR before or with the integration PR.
5. **Thin integration** — Single module or repo-root concern; port for anything business-facing.
6. **Documentation** — Update this matrix; migration reports under `private/design/migrations/` (local).

### 2. Forbidden patterns

| Pattern | Why forbidden |
|---------|---------------|
| `import hydra` in agents or workflow | Configuration is infrastructure; use `SettingsProvider` or config facade |
| `import pixi` or Pixi API in business code | Environment is repo-root concern only |
| Docling imports in Reader | Parsing isolated in adapters per ADR-0008 |
| Direct LLM SDK calls in agents | Use `LLMProvider` port |
| Infrastructure tool without ADR | No audit trail; breaks replaceability |

### 3. Native vs external boundary

| Layer | Native | External |
|-------|--------|----------|
| Analysis / Planning / Implementation agents | Agent logic, prompts, validation | — |
| Parsing | `DocumentParser` port, `ParsedDocument` | Docling, PyMuPDF libraries |
| Configuration | `SettingsProvider`, `AppSettings`, facade | Hydra, OmegaConf |
| Developer environment | Pixi tasks as repo convention | Pixi tool, conda-forge |
| Reproduction execution | `EnvironmentService`, `ExecutionService` | pip, subprocess, system Python in workspace |
| LLM | `LLMProvider`, response parsing | OpenAI, Anthropic SDKs |

### 4. When not to adopt external tools

- Man1Lab already has a native abstraction that suffices
- The tool would become visible to more than one integration point
- Adoption requires business-layer imports
- The problem is domain-specific reproduction logic (belongs in agents, not infra)

### 5. Deprecation

Retiring infrastructure (e.g. removing `requirements.txt` or `config.py` facade) requires:

- Updated ADR status or superseding ADR
- Migration report in `private/design/migrations/` (local)
- Update to this adoption matrix

### 6. Relationship to ARCHITECTURE.md

| Document | Scope |
|----------|-------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Platform layers, domain object, data flow, non-goals |
| **infrastructure.md** (this document) | Tool adoption, external vs native, governance process |
| [ADR index](../adr/README.md) | Individual decision records with context and alternatives |

Do not duplicate ADR rationale here. Link to ADRs for "why."

---

## Document Maintenance

| Event | Action |
|-------|--------|
| New infrastructure ADR | Add row to Technology Adoption Matrix |
| Phase 2 completion | Update Status column; move items out of Pending Research |
| Tool removed | Mark Deprecated in matrix; reference superseding ADR |
| Boundary violation found | Document in review; fix via thin-integration refactor |

**Last aligned with:** Man1Lab v1.1.0 — Foundation Release (2026-06-30)
