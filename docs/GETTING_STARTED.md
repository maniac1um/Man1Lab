# Getting Started

Quick orientation for installing and running Man1Lab v1.2.2. For implementation state, see [CURRENT_STATUS.md](CURRENT_STATUS.md).

---

## Prerequisites

- Python 3.10+
- **Pixi** (recommended for development) or **pip**

---

## 1. Install

### Pip (recommended for users)

```bash
pip install man1lab
```

From a source checkout:

```bash
git clone https://github.com/maniac1um/Man1Lab.git
cd Man1Lab
pip install -e .
```

### Pixi (recommended for development)

```bash
git clone https://github.com/maniac1um/Man1Lab.git
cd Man1Lab
pixi install
```

---

## 2. Initialize

Create workspace directories, cache paths, and a `.env` template (never overwrites existing files):

```bash
man1lab init
```

After workspace setup, `init` optionally prompts **Configure your first AI model?** — an interactive wizard for profile name, provider (OpenAI / DeepSeek / Anthropic), model, API key, and optional settings. Profiles are saved through the Model Registry (no manual YAML editing). Press `n` or use `--skip-model-config` for the same behavior as previous releases.

With Pixi:

```bash
pixi run man1lab init
```

Edit `.env` and add LLM API keys if you skipped the wizard. Optionally set `GITHUB_TOKEN` for GitHub discovery.

---

## 3. Doctor

Validate the runtime environment:

```bash
man1lab doctor
```

Checks include Python, Pixi, Git, GitHub token, workspace paths, configuration, Docling, MLflow, write permissions, network connectivity, and an **LLM** section (profile count, active profile, provider, model, API key, connection health, validation). Warnings do not fail the command; only critical failures return a non-zero exit code.

---

## 4. Clean

Remove regeneratable workspace artifacts without touching configuration, papers, or source code.

**SAFE mode (default)** removes `outputs/`, `logs/`, `mlruns/`, tool caches (`.pytest_cache`, `.mypy_cache`, `.ruff_cache`), `__pycache__/` directories, and `workspace/cache/` + `workspace/tmp/`. It preserves `workspace/tasks/`, `workspace/papers/`, `conf/`, and `.env`.

```bash
man1lab clean
man1lab clean --dry-run
```

**ALL mode** additionally removes `workspace/tasks/` and `workspace/artifacts/`. Confirmation is required unless you pass `--yes`:

```bash
man1lab clean --all
man1lab clean --all --yes
```

Lifecycle flow: `init` → `doctor` → reproduce → `clean`. The CLI delegates to `Man1Lab.clean()`; cleanup logic lives only in `application/lifecycle/`.

---

## 5. Reproduce

Run the complete reproduction workflow on a PDF:

```bash
man1lab reproduce paper.pdf
```

Set `PAPER_PATH` in `.env` to use the default paper path from configuration.

---

## Platform Workflow

`man1lab reproduce` runs the full platform pipeline through the **Platform Facade**:

```text
man1lab reproduce paper.pdf
        ↓
Analysis (Reader)
        ↓
Discovery (DiscoveryWorkflow)
        ↓
Execution Planning (ExecutionPlanningWorkflow)
        ↓
Planner
        ↓
Coder → Runner → Verification → Review → Report
```

**Public interfaces:** CLI (`man1lab`) and Python SDK (`from man1lab import Man1Lab`) — both delegate to `Man1Lab`; no direct workflow imports.

**Execution Planning (v1.2.1):** Complete. Six embedded providers commit deterministic engineering decisions via the shared Decision Foundation. See [architecture/EXECUTION_PLANNING.md](architecture/EXECUTION_PLANNING.md).

**Partial commands:** `man1lab analyze`, `man1lab discover`, `man1lab plan` — see `man1lab --help`.

---

## 6. Analyze (partial workflow)

Run analysis (Reader) only:

```bash
man1lab analyze paper.pdf
```

Other partial commands: `discover`, `plan`, `execute`. See `man1lab --help`.

---

## 7. Python SDK

```python
from man1lab import Man1Lab

client = Man1Lab()
client.init()
print(client.doctor())
report = client.reproduce("paper.pdf")
print(client.version())
```

The SDK delegates exclusively to the Platform Facade.

---

## API Key Configuration

Copy `.env.example` to `.env` if `man1lab init` did not create one:

```bash
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-pro
GITHUB_TOKEN=ghp_your-token
```

Without API keys, mock LLM providers return deterministic fixtures for tests.

### Model profiles (advanced)

Hydra configuration supports named model profiles under `conf/llm/default.yaml`:

```yaml
llm:
  active: default
  profiles:
    default:
      provider: openai
      model: gpt-4o-mini
      api_key_reference: OPENAI_API_KEY
    deepseek:
      provider: deepseek
      model: deepseek-chat
      base_url: https://api.deepseek.com
      api_key_reference: OPENAI_API_KEY
      enabled: false
    claude:
      provider: anthropic
      model: claude-sonnet-4
      api_key_reference: ANTHROPIC_API_KEY
      enabled: false
```

Set `ANTHROPIC_API_KEY` in `.env` and switch `active: claude` to use Anthropic. Business agents remain unaware of the provider — resolution happens inside `LLMManager` → `ModelRegistry` → `ProviderRegistry`.

### Model management CLI

Manage profiles without editing YAML directly:

```bash
man1lab model list
man1lab model current
man1lab model use claude
man1lab model add
man1lab model remove claude --force
man1lab model rename claude claude-prod
man1lab model test
man1lab model test claude
man1lab model validate
man1lab model export profiles.yaml
man1lab model import profiles.yaml
man1lab model import profiles.yaml --replace
man1lab model import profiles.yaml --skip-existing
```

Profile changes persist to `conf/llm/user_profiles.yaml`. Export writes a portable format (`profiles` + `active` only — never API keys). Import validates and merges profiles without contacting providers. The CLI delegates exclusively to `Man1Lab` facade methods.

Legacy `.env` variables (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `ANTHROPIC_API_KEY`) continue to work. When no profiles are configured, Man1Lab auto-migrates them into a `default` profile at runtime.

---

## Experiment Tracking (optional)

Each reproduction can be recorded as one MLflow experiment run. Default store: `sqlite:///mlruns/mlflow.db`. Disable with `TRACKING_BACKEND=noop`.

```bash
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db
```

---

## Integration Run (maintainers)

```bash
pixi run integration
```

Requires a configured API key. Results: `outputs/` and `logs/`.

---

## Running Tests

```bash
pixi run test
```

Or after `pip install -e ".[dev]"`:

```bash
python -m pytest tests/ -v
```

Current suite: **614 tests** (see [CURRENT_STATUS.md](CURRENT_STATUS.md)).

---

## Recommended Reading Order

1. [CURRENT_STATUS.md](CURRENT_STATUS.md)
2. [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md)
3. [architecture/EXECUTION_PLANNING.md](architecture/EXECUTION_PLANNING.md)
4. [ROADMAP.md](../ROADMAP.md)
5. [architecture/CAPABILITIES.md](architecture/CAPABILITIES.md)
6. [releases/v1.2.2.md](releases/v1.2.2.md)
7. [CHANGELOG.md](../CHANGELOG.md)
