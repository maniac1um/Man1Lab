# Man1Lab

**Engineering-first autonomous research paper reproduction platform.**

Man1Lab automates the engineering workflow behind AI paper reproduction — from reading a PDF to discovering official code and checkpoints, planning how to run the work, and driving implementation through a structured pipeline. One command. One platform.

[![PyPI version](https://img.shields.io/pypi/v/man1lab)](https://pypi.org/project/man1lab/)
[![Python Version](https://img.shields.io/pypi/pyversions/man1lab)](https://pypi.org/project/man1lab/)
[![Latest Release](https://img.shields.io/github/v/release/maniac1um/Man1Lab)](https://github.com/maniac1um/Man1Lab/releases)
[![Tests](https://img.shields.io/badge/tests-614%20passing-brightgreen)](docs/CURRENT_STATUS.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-Getting%20Started-blue)](docs/GETTING_STARTED.md)

---

## Why Man1Lab?

Reproducing a modern AI paper is an engineering project, not a reading exercise.

Researchers and engineers routinely spend days on work that follows the same pattern:

| Pain point | What you do today |
|------------|-------------------|
| Understand the paper | Read, highlight, and manually extract methods and requirements |
| Find official resources | Search GitHub, Hugging Face, and project pages by hand |
| Locate checkpoints and data | Track down weights, configs, and dataset links across sites |
| Prepare the environment | Create repos, install dependencies, wire configs manually |
| Bridge paper → code | Map sections of the paper to modules, scripts, and training steps |
| Connect everything | Stitch analysis, resources, and execution into one coherent plan |

**Man1Lab automates this engineering workflow.**

Give it a paper. It produces structured analysis, discovers resources, commits an execution strategy, and runs the reproduction pipeline — so you start from engineering decisions, not from scratch.

---

## Core Workflow

```text
Paper
  ↓
Analysis          — Extract reproduction requirements from the PDF
  ↓
Discovery         — Find official repositories, checkpoints, and datasets
  ↓
Execution Planning — Commit how the work should be engineered
  ↓
Execution         — Plan tasks, generate code, run training, verify, report
```

Each stage produces a structured artifact that feeds the next. The full pipeline is available through the CLI and Python SDK.

---

## Key Features

| Capability | Description | Status |
|------------|-------------|--------|
| Paper Analysis | Structured extraction from research PDFs | ✅ |
| Research Resource Discovery | Evidence-backed search for repos, models, and data | ✅ |
| Execution Planning | Engineering strategy before implementation | ✅ |
| CLI | `man1lab` — init, reproduce, model management, and more | ✅ |
| Python SDK | `from man1lab import Man1Lab` | ✅ |
| Multi-model Support | Switch LLM providers without editing config files | ✅ |
| Model Registry | Named profiles, active model, portable export/import | ✅ |
| OpenAI | GPT-family models | ✅ |
| DeepSeek | DeepSeek API-compatible models | ✅ |
| Anthropic | Claude models | ✅ |
| Package Distribution | `pip install man1lab` | ✅ |
| Platform Facade | Single entry point for CLI, SDK, and future interfaces | ✅ |

---

## Current Scope

Man1Lab targets **engineering-oriented software reproduction** of AI research papers.

| Domain | Supported as software reproduction |
|--------|-------------------------------------|
| Computer Vision | ✅ |
| Embodied AI (software stack) | ✅ |
| LLM Systems | ✅ |
| Agent Frameworks | ✅ |
| Reinforcement Learning | ✅ |

**What Man1Lab does:** automate analysis, resource discovery, execution planning, and the software reproduction pipeline.

**What is outside current scope:** physical robot deployment, hardware setup, calibration, and real-world deployment. Those remain manual engineering work. Man1Lab focuses on the software path from paper to runnable reproduction.

---

## Quick Start

```bash
pip install man1lab
man1lab init
man1lab doctor
man1lab reproduce paper.pdf
```

During `init`, you can configure your first LLM provider interactively. Full installation and configuration: [Getting Started](docs/GETTING_STARTED.md).

---

## Example Workflow

```bash
man1lab reproduce OpenVLA.pdf
```

```text
Analysis completed
  ↓
Official repository discovered
  ↓
Checkpoint and dataset candidates ranked
  ↓
Execution strategy generated
  ↓
Engineering tasks planned → repository built → training run → report
```

The platform handles the chain from paper to execution. You review outputs and iterate on results.

---

## Project Architecture

```text
Platform
  ↓
Analysis → Discovery → Execution Planning → Execution
```

Man1Lab is organized as a single platform with a clear stage-by-stage pipeline. Interfaces (CLI, SDK) delegate to one composition root — no direct coupling to internal agents from user code.

Details: [Architecture](docs/architecture/ARCHITECTURE.md)

---

## Roadmap

| Version | Focus | Status |
|---------|-------|--------|
| **v1.2.x** | Platform foundation, Execution Planning, CLI, SDK, multi-model support | **Completed** |
| **v1.3** | Repository Understanding — semantic mapping of discovered code to paper modules | Planned |
| **v1.4** | Repository Adaptation — align discovered repos with paper requirements | Planned |
| **v1.5** | Knowledge Memory — cross-run reproduction knowledge | Planned |

Live status: [Current Status](docs/CURRENT_STATUS.md) · Full roadmap: [ROADMAP.md](ROADMAP.md)

---

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/GETTING_STARTED.md) | Install, configure models, run your first reproduction |
| [Architecture](docs/architecture/ARCHITECTURE.md) | Platform design and canonical artifacts |
| [Current Status](docs/CURRENT_STATUS.md) | Capabilities, tests, and known limitations |
| [Release Notes](docs/releases/v1.2.2.md) | v1.2.2 — LLM platform and first-run experience |
| [Contributing](CONTRIBUTING.md) | Development setup and contribution guidelines |
| [Security](SECURITY.md) | Vulnerability reporting |
| [Support](SUPPORT.md) | Questions, bugs, and feature requests |

---

## Community

| Channel | Use for |
|---------|---------|
| [GitHub Issues](https://github.com/maniac1um/Man1Lab/issues) | Bug reports and feature requests |
| [GitHub Discussions](https://github.com/maniac1um/Man1Lab/discussions) | Questions and ideas |
| [Pull Requests](https://github.com/maniac1um/Man1Lab/pulls) | Code contributions ([guidelines](CONTRIBUTING.md)) |
| [Security Advisories](https://github.com/maniac1um/Man1Lab/security/advisories/new) | Private vulnerability reports only |

Man1Lab is an active research prototype for academic demonstration. See [Contributing](CONTRIBUTING.md) before opening large changes.

---

## Citation

```bibtex
@software{man1lab_2026,
  author       = {maniac1um},
  title        = {Man1Lab: An Autonomous Research Paper Reproduction Platform},
  year         = {2026},
  version      = {1.2.2},
  url          = {https://github.com/maniac1um/Man1Lab},
  note         = {Engineering-first autonomous research paper reproduction platform.}
}
```

Also see [CITATION.cff](CITATION.cff).

---

## License

Man1Lab is released under the MIT License. See the `LICENSE` file for details.

---

**Maintainer:** [maniac1um](https://github.com/maniac1um)
