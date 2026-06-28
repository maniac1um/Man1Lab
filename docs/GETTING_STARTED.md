# Getting Started

Quick orientation for new contributors. For current implementation state, see [CURRENT_STATUS.md](CURRENT_STATUS.md).

---

## Project Overview

ResearchAgent MVP is an automated pipeline that reads a research paper (PDF), plans engineering tasks, generates a reproduction repository, runs the training script, verifies results, and produces a final report.

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

1. [CURRENT_STATUS.md](CURRENT_STATUS.md) — what is implemented and what is blocked today
2. [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) — system architecture (note: some status tables may lag CURRENT_STATUS)
3. [DEVELOPMENT.md](../DEVELOPMENT.md) — milestone workflow, freeze policy, commit conventions
4. [adr/README.md](adr/README.md) — architecture decision records
5. [reviews/README.md](reviews/README.md) — milestone and integration review index
6. [roadmap/ROADMAP.md](roadmap/ROADMAP.md) — long-term timeline

Read individual milestone design reviews only when working on or auditing a specific capability.
