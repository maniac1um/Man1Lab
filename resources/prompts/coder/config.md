Generate a YAML configuration file for the reproduction project.

MANDATORY constraints:
- MUST fulfill the configuration role defined in the repository contract.
- MUST use a consistent top-level key layout that downstream scripts and modules will read.
- MUST expose keys that match the configuration role must_expose fields.
- REQUIRED: Downstream files will read ONLY keys recorded in the interface registry.

Include only configuration relevant to the target file path.
