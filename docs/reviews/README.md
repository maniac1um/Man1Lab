# Review Documents

Index of milestone design reviews, integration validation reports, integration fix analyses, and documentation governance records.

For current implementation state, see [CURRENT_STATUS.md](../CURRENT_STATUS.md).

---

## Document Types

| Type | Typical filename | Purpose |
|------|------------------|---------|
| Design review | `design_review.md` | Factual report at milestone completion |
| Integration report | `integration_report.md` | End-to-end pipeline validation |
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
| M7.F | [design_review.md](M7.F/design_review.md) | Documentation governance (Phase 1) | Active |

---

## Integration Validation

End-to-end pipeline runs against a real paper.

| Name | Document | Purpose | Lifecycle |
|------|----------|---------|-----------|
| M7.1 | [integration_report.md](M7.1/integration_report.md) | First E2E integration validation (mock LLM run) | Historical |

For the latest integration outcome, see [CURRENT_STATUS.md](../CURRENT_STATUS.md) and [integration_fix_02/validation_report.md](integration_fix_02/validation_report.md).

---

## Integration Fixes

Product integration fixes addressing observed E2E failures. Not capability milestones.

| Fix | Documents | Purpose | Lifecycle |
|-----|-----------|---------|-----------|
| integration_fix_01 | [failure_analysis.md](integration_fix_01/failure_analysis.md) | Failure analysis after first real-LLM integration run | Frozen |
| integration_fix_02 | [design_review.md](integration_fix_02/design_review.md) | Repository consistency fix design | Frozen |
| integration_fix_02 | [validation_report.md](integration_fix_02/validation_report.md) | Post-fix engineering validation | Active |

**Dependency chain:** fix_01 (analysis) → fix_02 (design + validation)

---

## Documentation Governance

Meta-documentation for documentation structure and maintenance.

| Phase | Documents | Purpose | Lifecycle |
|-------|-----------|---------|-----------|
| Phase 1 (audit) | [documentation_audit.md](documentation_governance_phase1/documentation_audit.md) | Documentation inventory and gap analysis | Frozen |
| Phase 1 (audit) | [restructuring_plan.md](documentation_governance_phase1/restructuring_plan.md) | Proposed restructure (not executed) | Historical |
| Phase 1 (audit) | [migration_checklist.md](documentation_governance_phase1/migration_checklist.md) | Migration plan (deferred) | Historical |
| M7.F | [design_review.md](M7.F/design_review.md) | Documentation governance implementation | Active |

---

## Which Review Should I Read?

| Goal | Start here |
|------|------------|
| Understand current project state | [CURRENT_STATUS.md](../CURRENT_STATUS.md) |
| Audit a specific capability | Milestone design review for that capability |
| Debug integration failures | [integration_fix_02/validation_report.md](integration_fix_02/validation_report.md) |
| Trace root cause history | [integration_fix_01/failure_analysis.md](integration_fix_01/failure_analysis.md) |
| Understand doc structure plans | [documentation_governance_phase1/](documentation_governance_phase1/) |

---

## Guidelines

- Reviews describe state at completion; do not rewrite frozen reports
- Link to ADRs instead of duplicating decision rationale
- Store new milestone reviews under `docs/reviews/{milestone}/design_review.md`
