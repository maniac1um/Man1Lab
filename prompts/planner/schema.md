Return a single JSON object with exactly these keys:

- paper_title
- tasks

Each item in tasks must be an object with:

- id
- name
- description
- depends_on (list of task id strings)

Order tasks in execution sequence.

Do not include markdown fences or extra commentary.
Return JSON only.
