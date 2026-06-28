# ResearchAgent MVP

ResearchAgent is an engineering pipeline for automated research paper reproduction. Given a research paper in PDF form, the system extracts structured paper information, plans engineering tasks, generates a reproduction repository, prepares a Python environment, executes the training script, verifies results, and produces a final report.

## Status

See **[docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md)** for implemented capabilities, pipeline state, latest integration result, and active issues.

New contributors: start with **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**.

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt`

## Running

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python app.py
```

Set `PAPER_PATH` to point to a PDF file.

### LLM configuration (DeepSeek / OpenAI-compatible)

Copy `.env.example` to `.env` and set:

```bash
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-pro
```

`config.py` loads `.env` automatically. Without `OPENAI_API_KEY`, mock providers are used.

## Documentation

| Document | Location |
|----------|----------|
| **Current status** | [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) |
| **Getting started** | [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) |
| Documentation index | [docs/README.md](docs/README.md) |
| Development guide | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Architecture | [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) |
| Reviews | [docs/reviews/README.md](docs/reviews/README.md) |
| ADRs | [docs/adr/README.md](docs/adr/README.md) |

## Project Structure

```text
agents/          # Reader, Planner, Coder, Runner, Reviewer, Reporter
models/          # Pydantic domain models
workflow/        # WorkflowOrchestrator
services/        # PDF, environment, execution, verification services
execution/       # ExecutionPlanner
planning/        # PatchPlanner
workspace/       # WorkspaceManager
prompt/          # Prompt loader and builder
llm/             # LLM provider abstraction
tests/           # Unit and integration tests
docs/            # Architecture, roadmap, ADRs, reviews
```
