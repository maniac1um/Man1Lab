Example when no iteration is required:

{
  "requires_patch": false,
  "priority": "LOW",
  "targets": [],
  "reason": "ReviewReport indicates verification passed with low risk.",
  "strategy": "Proceed to final reporting without another workflow iteration."
}

Example when another iteration is required:

{
  "requires_patch": true,
  "priority": "HIGH",
  "targets": ["execution"],
  "reason": "ReviewReport identifies execution failure requiring another workflow pass.",
  "strategy": "Schedule another reproduction workflow iteration focused on execution recovery."
}
