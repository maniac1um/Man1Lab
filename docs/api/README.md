# API Documentation

This directory will contain public API reference documentation for ResearchAgent modules.

## Purpose

Provide a stable, human-readable reference for contributors and integrators covering:

- Agent public methods and type contracts
- Domain model field definitions
- Service interfaces (`PDFService`, `PromptLoader`, `WorkspaceManager`)
- Workflow orchestrator entry points

## Planned Structure

```text
api/
    README.md
    agents.md
    models.md
    services.md
    workflow.md
```

## Current State

No API reference documents exist yet. Public APIs are defined in source code and described in:

- [Architecture](../architecture/ARCHITECTURE.md)
- [ADRs](../adr/README.md)
- Milestone design review reports under [reviews/](../reviews/)

API documentation will be added as interfaces stabilize through M8.

## Guidelines (Future)

- Document public methods only; omit private helpers
- Include input types, output types, and raised exceptions
- Keep examples minimal and runnable
- Update API docs in the same milestone that changes a frozen interface
