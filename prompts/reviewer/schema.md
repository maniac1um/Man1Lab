Return a single JSON object with exactly these keys:

- summary
- analysis
- identified_issues (list of strings)
- strengths (list of strings)
- risk_level (one of: LOW, MEDIUM, HIGH)
- next_action

The report must describe reproduction status only.
Do not include patches, code changes, or repair instructions.
Do not include markdown fences or extra commentary.
Return JSON only.
