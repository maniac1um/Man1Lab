# Review Documents

Index of milestone design reviews, integration validation reports, product integration fixes, and documentation governance records.

For **current** implementation state, see [CURRENT_STATUS.md](../CURRENT_STATUS.md).  
For **v1.0.0 release governance**, see [release_preparation/documentation_review.md](release_preparation/documentation_review.md).

---

## Document Types

| Type | Typical filename | Purpose |
|------|------------------|---------|
| Design review | `design_review.md` | Factual report at milestone completion |
| Integration report | `integration_report.md` | End-to-end pipeline validation |
| Acceptance report | `acceptance_report.md` | MVP acceptance observation |
| Implementation review | `implementation_review.md` | Post-design implementation validation |
| Failure analysis | `failure_analysis.md` | Post-integration defect catalog |
| Validation report | `validation_report.md` | Post-fix engineering validation |
| Governance audit | `documentation_audit.md` | Documentation structure assessment |

---

## Lifecycle

| Label | Meaning |
|-------|---------|
| **Active** | Describes current process or latest validation |
| **Frozen** | Accurate snapshot at completion; retained as audit record |
| **Historical** | Superseded or ad-hoc; retained, not primary reference |

---

## Milestone Reviews

Capability delivery reports. Directory layout: `docs/reviews/{milestone}/`.

| Milestone | Document | Purpose | Lifecycle |
|-----------|----------|---------|-----------|
| M4.1 | [design_review.md](M4.1/design_review.md) | Workspace construction | Frozen |
| M4.1 | [cursor_report.md](M4.1/cursor_report.md) | Early agent-assisted review | Historical |
| M4.2 | [design_review.md](M4.2/design_review.md) | Task routing | Frozen |
| M4.3 | [design_review.md](M4.3/design_review.md) | Repository population | Frozen |
| M5.1 | [design_review.md](M5.1/design_review.md) | Environment preparation | Frozen |
| M5.1.1 | [design_review.md](M5.1.1/design_review.md) | Runtime artifact ownership | Frozen |
| M5.2 | [design_review.md](M5.2/design_review.md) | Script execution | Frozen |
| M5.F | [design_review.md](M5.F/design_review.md) | Capability freeze (Reader–Runner) | Frozen |
| M6.1 | [design_review.md](M6.1/design_review.md) | Reproduction verification | Frozen |
| M6.2 | [design_review.md](M6.2/design_review.md) | LLM review | Frozen |
| M6.3 | [design_review.md](M6.3/design_review.md) | Patch planning | Frozen |
| M7.F | [design_review.md](M7.F/design_review.md) | Documentation governance (Phase 1) | Frozen |

---

## Integration Validation

End-to-end pipeline runs against real papers.

| Name | Document | Purpose | Lifecycle |
|------|----------|---------|-----------|
| M7.1 | [integration_report.md](M7.1/integration_report.md) | First E2E integration (mock LLM) | Historical |
| M8.1 | [acceptance_report.md](M8.1/acceptance_report.md) | MVP acceptance run (ResNet) | Frozen |
| M8.2 | [cross_paper_acceptance_report.md](M8.2/cross_paper_acceptance_report.md) | Cross-paper verification (DeiT) | Frozen |

For the latest benchmark summary, see [CURRENT_STATUS.md](../CURRENT_STATUS.md).

---

## Product Integration Fixes

Integration fixes addressing observed E2E failures. Not capability milestones.

| Fix | Documents | Purpose | Lifecycle |
|-----|-----------|---------|-----------|
| integration_fix_01 | [failure_analysis.md](integration_fix_01/failure_analysis.md) | Failure analysis after first real-LLM run | Frozen |
| integration_fix_02 | [design_review.md](integration_fix_02/design_review.md) | Repository consistency fix design | Frozen |
| integration_fix_02 | [validation_report.md](integration_fix_02/validation_report.md) | Post-fix engineering validation | Historical |
| integration_fix_03 | [design_review.md](integration_fix_03/design_review.md) | Integration fix #3 design | Frozen |
| integration_fix_03 | [implementation_review.md](integration_fix_03/implementation_review.md) | Integration fix #3 implementation | Frozen |
| integration_fix_04 | [generation_quality_analysis.md](integration_fix_04/generation_quality_analysis.md) | Generation quality root-cause analysis | Frozen |

**Dependency chain:** fix_01 → fix_02 → fix_03/04 → GQ-1 → RAG

---

## Post-MVP Quality Milestones

| Milestone | Document | Purpose | Lifecycle |
|-----------|----------|---------|-----------|
| GQ-1 | [implementation_review.md](generation_quality_upgrade_v1/implementation_review.md) | Generation quality upgrade v1 | Frozen |
| RAG | [implementation_review.md](repository_acceptance_gate/implementation_review.md) | Repository acceptance gate | Frozen |

---

## Documentation Governance

Meta-documentation for documentation structure and maintenance.

| Phase | Documents | Purpose | Lifecycle |
|-------|-----------|---------|-----------|
| Phase 1 (audit) | [documentation_audit.md](documentation_governance_phase1/documentation_audit.md) | Documentation inventory and gap analysis | Frozen |
| Phase 1 (audit) | [restructuring_plan.md](documentation_governance_phase1/restructuring_plan.md) | Proposed restructure (not executed) | Historical |
| Phase 1 (audit) | [migration_checklist.md](documentation_governance_phase1/migration_checklist.md) | Migration plan (deferred) | Historical |
| M7.F | [design_review.md](M7.F/design_review.md) | Documentation governance Phase 1 implementation | Frozen |
| v1.0.0 release | [documentation_review.md](release_preparation/documentation_review.md) | Release documentation governance pass | Frozen |
| v1.0.0 packaging | [release_review.md](release_packaging/release_review.md) | GitHub release asset preparation | Active |

---

## Which Review Should I Read?

| Goal | Start here |
|------|------------|
| Understand current project state | [CURRENT_STATUS.md](../CURRENT_STATUS.md) |
| Audit a specific capability | Milestone design review for that capability |
| Understand MVP acceptance evidence | [M8.1](M8.1/acceptance_report.md), [M8.2](M8.2/cross_paper_acceptance_report.md) |
| Understand Coder quality layers | [GQ-1](generation_quality_upgrade_v1/implementation_review.md), [RAG](repository_acceptance_gate/implementation_review.md) |
| Trace root cause history | [integration_fix_01](integration_fix_01/failure_analysis.md) through [integration_fix_04](integration_fix_04/generation_quality_analysis.md) |
| Understand doc structure plans | [documentation_governance_phase1/](documentation_governance_phase1/) |

---

## Guidelines

- Reviews describe state at completion; do not rewrite frozen reports
- Link to ADRs instead of duplicating decision rationale
- Store new milestone reviews under `docs/reviews/{milestone}/design_review.md`
- Current-state questions belong in `CURRENT_STATUS.md`, not in historical reviews
