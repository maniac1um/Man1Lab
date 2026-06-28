# ResearchAgent MVP

ResearchAgent is an engineering pipeline for automated research paper reproduction. Given a research paper in PDF form, the system extracts structured paper information, plans engineering tasks, generates a reproduction repository, prepares a Python environment, and executes the training script.

## Current Pipeline

```text
Research Paper (PDF)
        ↓
Reader → PaperModel
        ↓
Planner → TaskModel
        ↓
Coder → Workspace
        ↓
Runner → ExecutionResult
        ↓
Reviewer (planned)
        ↓
Reporter → ReportModel
```

## Implemented Capabilities

| Capability | Description |
|------------|-------------|
| **Reader** | PDF ingestion, LLM structured extraction, `PaperModel` construction |
| **Planner** | Engineering task decomposition, `TaskModel` construction |
| **Coder** | Workspace skeleton, task routing, per-file LLM code generation |
| **Runner** | Environment preparation (venv, pip) and `scripts/train.py` execution |

## Planned Capabilities

| Capability | Description |
|------------|-------------|
| **Reviewer** | Execution failure analysis and `PatchPlan` generation |
| **Reporter** | Full structured final reporting (partial template exists) |

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt`

## Running

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python app.py
```

Set `PAPER_PATH` to point to a PDF file. Set `OPENAI_API_KEY` for real LLM extraction; without it, mock providers are used.

## Documentation

| Document | Location |
|----------|----------|
| Development guide | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Architecture | [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) |
| Capabilities | [docs/architecture/CAPABILITIES.md](docs/architecture/CAPABILITIES.md) |
| Roadmap | [docs/roadmap/ROADMAP.md](docs/roadmap/ROADMAP.md) |
| ADRs | [docs/adr/README.md](docs/adr/README.md) |

## Project Structure

```text
agents/          # Reader, Planner, Coder, Runner, Reviewer, Reporter
models/          # Pydantic domain models
workflow/        # WorkflowOrchestrator
services/        # PDF, environment, execution services
execution/       # ExecutionPlanner
workspace/       # WorkspaceManager
prompt/          # Prompt loader and builder
llm/             # LLM provider abstraction
tests/           # Unit and integration tests
docs/            # Architecture, roadmap, ADRs, reviews
```
