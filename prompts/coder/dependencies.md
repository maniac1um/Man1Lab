Generate a Python requirements file listing packages needed for the reproduction project.

MANDATORY constraints:
- MUST include every third-party package imported by generated Python files.
- MUST include framework_binding.required_primary_packages from the shared generation context.
- MUST NOT omit the bound framework's primary packages.
- REQUIRED: Use the interface registry import_roots when present.

Include only package names and version constraints. One package per line.
