"""Deterministic repository quality helpers for Coder (GQ-1)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

_TRAIN_ENTRYPOINT = "scripts/train.py"

# Finding codes that cause repository rejection at the acceptance gate.
_BLOCKING_FINDING_CODES = frozenset(
    {
        "import_not_in_requirements",
        "forbidden_framework_import",
        "framework_mixing",
        "framework_binding_violation",
        "import_not_in_registry",
        "missing_training_entrypoint",
    }
)

# Maps validation finding codes to acceptance gate categories.
_BLOCKING_CATEGORY_BY_CODE = {
    "import_not_in_requirements": "import_closure_failure",
    "forbidden_framework_import": "framework_binding_failure",
    "framework_mixing": "framework_binding_failure",
    "framework_binding_violation": "framework_binding_failure",
    "import_not_in_registry": "broken_internal_import",
    "missing_training_entrypoint": "missing_training_entrypoint",
}


class RepositoryAcceptanceError(Exception):
    """Raised when a generated repository fails deterministic acceptance checks."""

    def __init__(self, blocking_errors: list[dict[str, str]]) -> None:
        self.blocking_errors = blocking_errors
        summary = "; ".join(error["message"] for error in blocking_errors)
        super().__init__(f"Repository acceptance failed: {summary}")


_CONFIG_KEY_PATTERN = re.compile(
    r"""config(?:\[[^\]]+\]|\.get\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"])"""
)
_REQUIREMENT_NAME_PATTERN = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)",
)

# Import root -> PyPI distribution name (generic, not paper-specific).
_IMPORT_ROOT_TO_PACKAGE: dict[str, str] = {
    "torch": "torch",
    "torchvision": "torchvision",
    "numpy": "numpy",
    "cv2": "opencv-python",
    "yaml": "PyYAML",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "scipy": "scipy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "tqdm": "tqdm",
    "caffe": "caffe",
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    "jax": "jax",
    "flax": "flax",
    "protobuf": "protobuf",
    "tensorboard": "tensorboard",
}

_FRAMEWORK_PROFILES: dict[str, dict[str, object]] = {
    "pytorch": {
        "primary_packages": ["torch"],
        "required_import_roots": ["torch"],
        "forbidden_import_roots": ["caffe", "tensorflow", "tf", "jax"],
    },
    "tensorflow": {
        "primary_packages": ["tensorflow"],
        "required_import_roots": ["tensorflow", "tf"],
        "forbidden_import_roots": ["torch", "caffe", "jax"],
    },
    "jax": {
        "primary_packages": ["jax"],
        "required_import_roots": ["jax"],
        "forbidden_import_roots": ["torch", "caffe", "tensorflow", "tf"],
    },
    "caffe": {
        "primary_packages": ["caffe"],
        "required_import_roots": ["caffe"],
        "forbidden_import_roots": ["torch", "tensorflow", "tf", "jax"],
    },
}

_STDLIB_ROOTS = frozenset(
    {
        "__future__",
        "abc",
        "argparse",
        "collections",
        "contextlib",
        "copy",
        "dataclasses",
        "enum",
        "functools",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "os",
        "pathlib",
        "random",
        "re",
        "shutil",
        "subprocess",
        "sys",
        "tempfile",
        "time",
        "typing",
        "unittest",
        "urllib",
        "warnings",
    }
)


def build_framework_binding(framework: str) -> dict[str, object]:
    profile = resolve_framework_profile(framework)
    return {
        "framework": framework,
        "required_primary_packages": list(profile["primary_packages"]),
        "must_use_import_roots": list(profile["required_import_roots"]),
        "forbidden_import_roots": list(profile["forbidden_import_roots"]),
        "constraint": (
            "Every generated Python file MUST use only the bound framework stack. "
            "NEVER import forbidden framework roots listed above."
        ),
    }


def resolve_framework_profile(framework: str) -> dict[str, object]:
    key = framework.casefold().strip()
    for profile_key, profile in _FRAMEWORK_PROFILES.items():
        if profile_key in key:
            return profile
    return {
        "primary_packages": [],
        "required_import_roots": [],
        "forbidden_import_roots": [],
    }


def extract_python_import_roots(content: str) -> list[str]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _extract_import_roots_regex(content)

    roots: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.append(node.module.split(".")[0])
    return _dedupe_preserve_order(roots)


def extract_config_key_accesses(content: str) -> list[str]:
    keys: list[str] = []
    for match in _CONFIG_KEY_PATTERN.finditer(content):
        key = match.group(1)
        if key:
            keys.append(key)
    bracket_pattern = re.compile(r"""config\[['"]([A-Za-z_][A-Za-z0-9_]*)['"]\]""")
    for match in bracket_pattern.finditer(content):
        keys.append(match.group(1))
    return _dedupe_preserve_order(keys)


def import_root_to_package(import_root: str) -> str:
    return _IMPORT_ROOT_TO_PACKAGE.get(import_root, import_root)


def is_third_party_import(import_root: str) -> bool:
    if not import_root or import_root.startswith("src"):
        return False
    if import_root in _STDLIB_ROOTS:
        return False
    return True


def collect_required_packages(
    python_files: dict[str, str],
    framework: str,
) -> set[str]:
    packages: set[str] = set()
    profile = resolve_framework_profile(framework)
    for package in profile["primary_packages"]:
        if isinstance(package, str):
            packages.add(package)

    for content in python_files.values():
        for root in extract_python_import_roots(content):
            if is_third_party_import(root):
                packages.add(import_root_to_package(root))
    return packages


def parse_requirements_packages(requirements_content: str) -> set[str]:
    packages: set[str] = set()
    for line in requirements_content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _REQUIREMENT_NAME_PATTERN.match(stripped)
        if match:
            packages.add(match.group(1).casefold())
    return packages


def format_requirements(packages: set[str]) -> str:
    ordered = sorted(packages, key=str.casefold)
    return "\n".join(ordered) + "\n" if ordered else "# No third-party packages detected\n"


def reconcile_requirements_content(
    existing_content: str,
    required_packages: set[str],
) -> str:
    packages: dict[str, str] = {}
    for line in existing_content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _REQUIREMENT_NAME_PATTERN.match(stripped)
        if match:
            name = match.group(1)
            packages[name.casefold()] = name
    for package in required_packages:
        packages[package.casefold()] = package
    ordered = sorted(packages.values(), key=str.casefold)
    return "\n".join(ordered) + "\n" if ordered else "# No third-party packages detected\n"


def collect_python_files(workspace_root: Path, relative_paths: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for relative_path in relative_paths:
        if not relative_path.endswith(".py"):
            continue
        path = workspace_root / relative_path
        if path.is_file():
            files[relative_path] = path.read_text(encoding="utf-8")
    return files


def validate_generated_repository(
    *,
    workspace_root: Path,
    routed_paths: set[str],
    python_files: dict[str, str],
    requirements_content: str,
    framework_binding: dict[str, object],
    interface_registry: dict[str, object],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    for path in sorted(routed_paths):
        if path == "requirements.txt":
            continue
        full_path = workspace_root / path
        if not full_path.is_file():
            code = (
                "missing_training_entrypoint"
                if path == _TRAIN_ENTRYPOINT
                else "missing_routed_file"
            )
            severity = "error" if code == "missing_training_entrypoint" else "warning"
            findings.append(
                {
                    "severity": severity,
                    "code": code,
                    "message": f"Routed file missing: {path}",
                }
            )

    _append_training_entrypoint_findings(
        workspace_root,
        findings,
    )
    _append_framework_mixing_findings(python_files, findings)

    req_packages = parse_requirements_packages(requirements_content)
    for relative_path, content in sorted(python_files.items()):
        import_roots = extract_python_import_roots(content)
        for root in import_roots:
            if not is_third_party_import(root):
                continue
            package = import_root_to_package(root).casefold()
            if package not in req_packages:
                findings.append(
                    {
                        "severity": "error",
                        "code": "import_not_in_requirements",
                        "message": (
                            f"{relative_path} imports '{root}' "
                            f"but requirements.txt lacks '{package}'"
                        ),
                    }
                )

        forbidden = framework_binding.get("forbidden_import_roots", [])
        if isinstance(forbidden, list):
            for root in import_roots:
                if root in forbidden:
                    findings.append(
                        {
                            "severity": "error",
                            "code": "forbidden_framework_import",
                            "message": (
                                f"{relative_path} imports forbidden framework root "
                                f"'{root}' for {framework_binding.get('framework')}"
                            ),
                        }
                    )

    required_roots = framework_binding.get("must_use_import_roots", [])
    if isinstance(required_roots, list) and required_roots and python_files:
        all_roots = {
            root
            for content in python_files.values()
            for root in extract_python_import_roots(content)
        }
        if not any(root in all_roots for root in required_roots if isinstance(root, str)):
            findings.append(
                {
                    "severity": "error",
                    "code": "framework_binding_violation",
                    "message": (
                        f"No Python file imports required framework roots: "
                        f"{list(required_roots)}"
                    ),
                }
            )

    for relative_path, content in python_files.items():
        if not relative_path.startswith("scripts/"):
            continue
        if 'if __name__ == "__main__"' not in content and "if __name__ == '__main__'" not in content:
            findings.append(
                {
                    "severity": "warning",
                    "code": "missing_script_entrypoint_guard",
                    "message": f"{relative_path} lacks if __name__ == '__main__' guard",
                }
            )

        accessed_keys = extract_config_key_accesses(content)
        for config_path, entry in interface_registry.items():
            if not config_path.startswith("configs/"):
                continue
            if not isinstance(entry, dict):
                continue
            top_level_keys = entry.get("top_level_keys", [])
            if not isinstance(top_level_keys, list):
                continue
            for key in accessed_keys:
                if key not in top_level_keys:
                    findings.append(
                        {
                            "severity": "warning",
                            "code": "config_key_not_in_registry",
                            "message": (
                                f"{relative_path} accesses config key '{key}' "
                                f"not in registry for {config_path}"
                            ),
                        }
                    )

        registry_entry = interface_registry.get(relative_path)
        if isinstance(registry_entry, dict):
            imported_symbols = _extract_local_imports(content)
            for module_path, symbols in imported_symbols.items():
                upstream = interface_registry.get(module_path)
                if not isinstance(upstream, dict):
                    continue
                public_symbols = upstream.get("public_symbols", [])
                if not isinstance(public_symbols, list):
                    continue
                for symbol in symbols:
                    if symbol not in public_symbols:
                        findings.append(
                            {
                                "severity": "error",
                                "code": "import_not_in_registry",
                                "message": (
                                    f"{relative_path} imports '{symbol}' from "
                                    f"{module_path} but registry lists {public_symbols}"
                                ),
                            }
                        )

    return findings


def decide_repository_acceptance(
    findings: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    blocking_errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for finding in findings:
        code = finding.get("code", "")
        if code in _BLOCKING_FINDING_CODES:
            category = _BLOCKING_CATEGORY_BY_CODE.get(code, code)
            blocking_errors.append(
                {
                    "category": category,
                    "code": code,
                    "message": finding.get("message", ""),
                }
            )
        else:
            warnings.append(finding)
    return blocking_errors, warnings


def format_acceptance_log(
    *,
    accepted: bool,
    blocking_errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> str:
    status = "ACCEPTED" if accepted else "REJECTED"
    lines = [f"Repository acceptance gate: {status}", ""]
    if blocking_errors:
        lines.append("Blocking errors:")
        for error in blocking_errors:
            lines.append(
                f"  [{error['category']}] {error['code']}: {error['message']}"
            )
        lines.append("")
    if warnings:
        lines.append("Warnings (non-blocking):")
        for warning in warnings:
            lines.append(
                f"  [{warning.get('severity', 'warning').upper()}] "
                f"{warning.get('code', 'unknown')}: {warning.get('message', '')}"
            )
        lines.append("")
    if accepted and not warnings:
        lines.append("No warnings.")
    return "\n".join(lines).rstrip() + "\n"


def format_validation_log(findings: list[dict[str, str]]) -> str:
    if not findings:
        return "Generation validation: PASS (no findings)\n"
    lines = ["Generation validation findings:", ""]
    for finding in findings:
        lines.append(
            f"[{finding['severity'].upper()}] {finding['code']}: {finding['message']}"
        )
    return "\n".join(lines) + "\n"


def _append_training_entrypoint_findings(
    workspace_root: Path,
    findings: list[dict[str, str]],
) -> None:
    train_path = workspace_root / _TRAIN_ENTRYPOINT
    if not train_path.is_file():
        findings.append(
            {
                "severity": "error",
                "code": "missing_training_entrypoint",
                "message": (
                    f"Training entrypoint not found: {_TRAIN_ENTRYPOINT}"
                ),
            }
        )
        return
    if not train_path.read_text(encoding="utf-8").strip():
        findings.append(
            {
                "severity": "error",
                "code": "missing_training_entrypoint",
                "message": f"Training entrypoint is empty: {_TRAIN_ENTRYPOINT}",
            }
        )


def _append_framework_mixing_findings(
    python_files: dict[str, str],
    findings: list[dict[str, str]],
) -> None:
    all_roots = {
        root
        for content in python_files.values()
        for root in extract_python_import_roots(content)
    }
    frameworks_present: list[str] = []
    for profile_key, profile in _FRAMEWORK_PROFILES.items():
        required_roots = profile.get("required_import_roots", [])
        if not isinstance(required_roots, list):
            continue
        if any(root in all_roots for root in required_roots if isinstance(root, str)):
            frameworks_present.append(profile_key)
    if len(frameworks_present) > 1:
        findings.append(
            {
                "severity": "error",
                "code": "framework_mixing",
                "message": (
                    "Repository mixes multiple deep-learning frameworks: "
                    f"{frameworks_present}"
                ),
            }
        )


def _extract_local_imports(content: str) -> dict[str, list[str]]:
    imports: dict[str, list[str]] = {}
    pattern = re.compile(r"from (src\.\w+) import ([\w, ]+)")
    for match in pattern.finditer(content):
        module = match.group(1).replace(".", "/") + ".py"
        symbols = [part.strip() for part in match.group(2).split(",") if part.strip()]
        imports[module] = symbols
    return imports


def _extract_import_roots_regex(content: str) -> list[str]:
    roots: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            roots.append(stripped.split()[1].split(".")[0])
        elif stripped.startswith("from ") and " import " in stripped:
            module = stripped.split()[1]
            if not module.startswith("."):
                roots.append(module.split(".")[0])
    return _dedupe_preserve_order(roots)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
