# Project Structure

Man1Lab uses a `src` layout so product code, repository resources, runtime data,
tests, and maintenance tooling have distinct ownership.

```text
Man1Lab/
|-- src/             Python product packages and compatibility modules
|-- resources/       Version-controlled Hydra configuration and prompts
|-- var/             Generated workspaces, outputs, logs, and execution state
|-- scripts/         Maintainer and compatibility entry points
|-- tests/           Unit, integration, acceptance, and benchmark tests
|-- docs/            Architecture, guides, ADRs, and release documentation
|-- pyproject.toml   Build, package, and test configuration
|-- pixi.toml        Development environment and commands
`-- README.md        Project overview
```

## Ownership rules

- Add importable application code under `src/`; preserve top-level package names.
- Add static configuration and prompt assets under `resources/`.
- Write repository-level generated data only under `var/`. Generated files are
  ignored except for directory placeholders.
- Put maintainer scripts under `scripts/`; public interfaces remain the CLI and SDK.
- Keep the repository root for project metadata and the major category directories above.

An execution workspace may still contain its own `outputs/` and `logs/` folders.
Those are part of the reproduction artifact contract and are distinct from the
repository-level `var/outputs/` and `var/logs/` directories.
