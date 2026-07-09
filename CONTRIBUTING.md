# Contributing to Man1Lab

Thank you for your interest in contributing to Man1Lab.

Man1Lab is an engineering-first platform for AI research paper reproduction. We welcome bug reports, feature discussions, documentation improvements, and code contributions.

---

## Development Setup

Clone the repository:

```bash
git clone https://github.com/maniac1um/Man1Lab.git
cd Man1Lab
```

Install the development environment:

```bash
pixi install
```

Verify everything works:

```bash
pixi run test
pixi run man1lab --version
```

---

## Repository Structure

```text
interfaces/      CLI and SDK
application/     Platform Facade
workflow/        Capability orchestration
providers/       Infrastructure adapters
runtime/         Runtime platform
models/          Canonical data models
tests/           Unit and integration tests
docs/            Documentation
```

The CLI and SDK should always delegate through the **Platform Facade**.

---

## Development Principles

Please follow these architectural rules:

- CLI → Facade only
- SDK → Facade only
- Workflow → Services
- Services → Providers
- Providers never import workflow logic

Avoid introducing parallel implementations when an existing abstraction can be extended.

For architectural details, see:

- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/RUNTIME.md`

---

## Running Tests

Run the complete test suite before submitting changes.

```bash
pixi run test
```

For new functionality:

- add unit tests
- update existing tests when behavior changes
- keep all tests passing

---

## Pull Requests

Before opening a PR:

- Keep changes focused.
- Update documentation when necessary.
- Run the full test suite.
- Discuss large architectural changes in an Issue first.

Checklist:

- [ ] Tests pass
- [ ] Documentation updated
- [ ] No architecture boundary violations
- [ ] No breaking public API changes

---

## Coding Style

- Match the existing project style.
- Prefer small, focused commits.
- Avoid unnecessary refactoring.
- Keep business logic independent from infrastructure.

---

## Documentation

Useful references:

- Getting Started
- Architecture
- Runtime
- Current Status
- Roadmap
- ADRs

Architecture decisions should be documented through ADRs.

---

## Need Help?

- Bug reports → GitHub Issues
- Questions → GitHub Discussions
- Security issues → SECURITY.md

Thank you for helping improve Man1Lab.