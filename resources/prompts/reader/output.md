## Output contract

Return **one JSON object only**.

Requirements:
- Match the `PaperReproductionAnalysis` schema in the Schema section.
- Include all top-level keys: `schema_version`, `metadata`, `goal`, `resources`, `method`, `evaluation`, `reproduction_gaps`.
- Use `schema_version`: `"1.0"`.
- Do **not** return legacy flat fields (`abstract`, `dataset`, `model`, `evaluation_metric`, etc.).
- Do **not** wrap JSON in markdown fences.
- Do **not** add commentary, explanation, or prose before or after the JSON.
- Do **not** output Markdown, YAML, or plain-text summaries.

If information is missing: leave fields empty and record `reproduction_gaps`. Never infer. Never search. Never assume.
