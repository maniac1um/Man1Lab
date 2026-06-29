# Getting Started

Quick orientation for running and exploring the prototype. For current implementation state, see [CURRENT_STATUS.md](CURRENT_STATUS.md).

---

## Project Overview

Man1Lab v1.0.0 is an automated pipeline that reads a research paper (PDF), plans engineering tasks, generates a reproduction repository, runs the training script, verifies results, reviews failures, and produces a final report.

System design and agent boundaries are documented in [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md).

---

## Prerequisites

- Python 3.10+
- `pip` and a virtual environment (recommended)

---

## Installation

```bash
git clone <repository-url>
cd Research_Agent_MVP
pip install -r requirements.txt
```

---

## Running Tests

```bash
PYTHONPATH=. python -m pytest tests/ -v
```

Or with unittest:

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
```

Current suite: **126 tests** (see [CURRENT_STATUS.md](CURRENT_STATUS.md)).

---

## Running the Application

```bash
PYTHONPATH=. python app.py
```

Set `PAPER_PATH` to point to a PDF file (default: `paper.pdf` in the project root).

---

## API Key Configuration

Without an API key, the pipeline uses mock LLM providers (deterministic fixtures).

For real LLM calls, copy `.env.example` to `.env`:

```bash
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-pro
```

`config.py` loads `.env` automatically via `python-dotenv`.

### Integration run (full pipeline)

```bash
PYTHONPATH=. python scripts/run_integration_m7_1.py
```

Requires a configured API key. Results are written to `outputs/` and `logs/`.

---

## Recommended Reading Order

1. [CURRENT_STATUS.md](CURRENT_STATUS.md) — what is implemented, benchmarks, and limitations
2. [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) — system architecture
3. [architecture/CAPABILITIES.md](architecture/CAPABILITIES.md) — per-capability component reference
4. [DEVELOPMENT.md](../DEVELOPMENT.md) — milestone workflow, freeze policy, commit conventions
5. [adr/README.md](adr/README.md) — architecture decision records
6. [reviews/README.md](reviews/README.md) — milestone and integration review index
7. [roadmap/ROADMAP.md](roadmap/ROADMAP.md) — development timeline
8. [CHANGELOG.md](../CHANGELOG.md) — v1.0.0 release history
9. [release/v1.0.0.md](../release/v1.0.0.md) — GitHub Release notes

Read individual milestone design reviews only when auditing a specific capability or tracing historical decisions.
