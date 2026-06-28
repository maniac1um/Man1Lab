# ADR-0003 — Prompt Infrastructure

## Status

Accepted

## Date

2026-06-28

## Context

Multiple agents (Reader, Planner, Coder, Reviewer) will require LLM prompts stored as Markdown files. Without centralization, each agent would read files directly, duplicate path logic, and make prompt versioning and testing difficult.

## Decision

Prompt resources are treated as repository assets under `prompts/`. Two modules centralize all prompt access:

**`PromptLoader`** — loads individual prompt sections from `prompts/{agent}/{section}.md`. Caches loaded content. Raises `PromptNotFoundError` on missing files.

**`PromptBuilder`** — composes sections into final prompts via deterministic string concatenation. No template engine.

Agents depend on `PromptBuilder` (or future agent-specific builder methods), never on prompt file paths or `open()`.

Current Reader integration: `run()` calls `PromptBuilder.build_reader_prompt()` before extraction. The composed prompt is stored in `Reader._last_prompt` for debugging; it is not yet sent to an LLM.

## Alternatives

**Agents read Markdown directly:** Rejected; scatters filesystem logic, prevents caching and versioning.

**Jinja2 / template engine:** Rejected as over-engineering for MVP; simple concatenation is sufficient.

**Prompts embedded in Python strings:** Rejected; prevents non-developer editing and version control of prompt content.

**Plugin registry for prompt providers:** Rejected; unnecessary abstraction for current scale.

## Consequences

**Positive:**
- Single module owns prompt file paths
- Prompt composition order is explicit and testable
- Future versioning can add directory layers without agent changes
- Prompt files are editable without code changes

**Negative:**
- Only `build_reader_prompt()` exists; other agents need builders in future milestones
- `tools/prompt_loader.py` legacy module remains orphaned until removed
- `prompts/reader/output.md` is unused after `schema.md` was introduced

## Frozen Interface

`PromptLoader.load(agent, section)` and `PromptBuilder` public methods are architecture-frozen.
