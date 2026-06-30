# ADR-0008 — Document Parsing with Docling

## Status

Accepted

## Date

2026-06-30

## Context

During M2.1, the Reader agent extracted paper text via `PDFService` (PyMuPDF). Reader depended directly on that concrete service, coupling the Paper Analysis stage to a single extraction implementation.

PyMuPDF `page.get_text()` yields normalized plain text. Research PDFs contain headings, tables, figure captions, and multi-column layout. Flat text loses structure that helps the Paper Analysis LLM infer sections, methods, and results.

The Reader public contract is frozen by [ADR-0002](ADR-0002-Stable-Reader-Interface.md): `read_text(paper_path) -> str` and `run(paper_path) -> PaperModel` must remain stable. Any parsing change must be internal to Reader and must not alter downstream agents, `PaperModel`, or `WorkflowOrchestrator`.

## Decision

Replace PyMuPDF as the **default** paper parsing backend with **Docling**, using a **ports-and-adapters** layout so Reader depends on an abstraction, not a library.

### Architecture

```text
app.py / run_integration_m7_1.py
    ↓
Reader(document_parser=build_document_parser())
    ↓
adapters/factory.py
    ├─ PARSER_BACKEND=docling (default) → DoclingParser
    └─ PARSER_BACKEND=pymupdf         → PyMuPDFParser → PDFService
    ↓
DocumentParser.parse(paper_path) → ParsedDocument
    ↓
Reader.read_text() → ParsedDocument.markdown (str)
    ↓
Reader.run() → PaperModel   # unchanged
```

### Port: `DocumentParser`

`ports/document_parser.py` defines a structural `Protocol`:

| Method | Input | Output |
|--------|-------|--------|
| `parse(paper_path)` | `Path` | `ParsedDocument` |

Adapters implement the protocol without inheriting a base class. The factory returns any object satisfying the protocol.

### Value object: `ParsedDocument`

`ports/parsed_document.py` defines a frozen dataclass returned by all parsers:

| Field | Status |
|-------|--------|
| `markdown` | Populated today — primary text passed to the Paper Analysis LLM |
| `metadata`, `sections`, `figures`, `tables`, `equations`, `references` | Reserved for future structured exports without changing `DocumentParser` |

`Reader.read_text()` extracts `.markdown` only, preserving the ADR-0002 `str` return type. A future document-based API may expose the full `ParsedDocument` without breaking `run()`.

### Adapters

| Adapter | Backend | Output |
|---------|---------|--------|
| `adapters/docling_parser.py` | Docling + `PyPdfiumDocumentBackend` | Structured Markdown (headings, tables, reading order) |
| `adapters/pymupdf_parser.py` | Legacy `PDFService` (PyMuPDF) | Plain normalized text wrapped in `ParsedDocument(markdown=text)` |

### Factory and configuration

`adapters/factory.py` exposes `build_document_parser()`. It reads settings via `ParserSettingsProvider` (default: `ConfigParserSettingsProvider` from `config.PARSER_BACKEND`).

| Setting | Default | Purpose |
|---------|---------|---------|
| `PARSER_BACKEND` | `docling` | Select active adapter |
| `MAX_PAPER_TEXT_CHARS` | `80000` | Truncation at parser boundary before LLM |
| `output_format` | `MARKDOWN` | Docling export format (via `ports/output_format.py`) |

Docling pipeline options: `do_ocr=False`, `do_table_structure=True`. OCR is disabled because research PDFs typically have text layers; OCR avoids model-download failures and latency on text-native PDFs.

### Reader decoupling

`agents/reader.py` accepts `DocumentParser` in its constructor. It does **not** import Docling, PyMuPDF, or `PDFService`. Composition roots (`app.py`, `scripts/run_integration_m7_1.py`) wire `build_document_parser()`.

### Legacy retention

`services/pdf_service.py` and `PyMuPDFParser` remain for rollback. Set `PARSER_BACKEND=pymupdf` to restore the previous extraction path without code changes.

### Frozen interface preserved

Per ADR-0002, `Reader.run()` and `Reader.read_text()` signatures and return types are unchanged. `PaperModel`, Planner, Coder, Runner, and `WorkflowOrchestrator` require no changes.

## Alternatives

**Keep PyMuPDF only:** Rejected. Flat text degrades Paper Analysis quality on structured papers; does not address Reader–parser coupling.

**Import Docling directly in Reader:** Rejected. Violates dependency inversion; makes testing and backend swaps require Reader changes.

**Abstract base class instead of Protocol:** Rejected. Structural typing matches existing adapter style with minimal ceremony; no shared implementation to inherit.

**Separate `IngestionAgent`:** Rejected for MVP. Adds orchestrator complexity; parsing is an internal Reader concern per ADR-0002.

**Enable Docling OCR by default:** Rejected. Scanned PDFs are out of scope for the default path; OCR adds model load time and operational risk. Can be enabled later or routed via `PARSER_BACKEND=pymupdf` as interim fallback.

**Remove `PDFService` immediately:** Rejected. Feature-flag rollback and fast deterministic unit tests depend on the legacy backend until Docling is stable in production.

## Consequences

**Positive:**

- Default parsing produces structured Markdown, improving LLM context for headings, tables, and figure blocks
- Reader depends on `DocumentParser` only — backend swaps are wiring changes, not Reader edits
- `ParsedDocument` reserves fields for richer exports without breaking the protocol
- Rollback via `PARSER_BACKEND=pymupdf` requires no redeploy of Reader or workflow code
- ADR-0002 frozen Reader contract is fully preserved

**Negative:**

- Docling first run may download ML models (~minutes); ops must cache Hugging Face artifacts in CI/production
- Docling is slower per page than PyMuPDF; acceptable tradeoff for extraction quality
- `do_ocr=False` yields poor results on scanned PDFs; operators must use pymupdf fallback or enable OCR explicitly later
- Markdown output can exceed plain-text length; `MAX_PAPER_TEXT_CHARS` truncation remains active
- Composition roots changed from `Reader(pdf_service=PDFService())` to `Reader(document_parser=build_document_parser())` — wiring-only change, not a pipeline contract change
- Unit tests inject `PyMuPDFParser` for speed; Docling paths are covered by mocked unit tests

## Relationship to Existing ADRs

This ADR records the internal parsing layer only. [ADR-0002](ADR-0002-Stable-Reader-Interface.md) governs the frozen Reader public API; this decision changes implementation behind that API. [ADR-0001](ADR-0001-Workflow-Orchestrator.md) is unaffected — no orchestrator or agent communication changes.

## Verification

```bash
# Unit tests (PyMuPDFParser injection for deterministic runs)
PYTHONPATH=. pytest tests/ -q

# Production default (docling)
PARSER_BACKEND=docling PYTHONPATH=. python app.py

# Rollback
PARSER_BACKEND=pymupdf PYTHONPATH=. python app.py
```
