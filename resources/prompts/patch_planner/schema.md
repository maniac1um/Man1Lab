Return a single JSON object with exactly these keys:

- requires_patch (boolean)
- priority (one of: LOW, MEDIUM, HIGH)
- targets (list of workflow area strings, e.g. repository, environment, execution, output)
- reason (string)
- strategy (string)

The output must describe workflow decisions only.
Do not include code, file paths, diffs, or edit instructions.
Do not include markdown fences or extra commentary.
Return JSON only.
