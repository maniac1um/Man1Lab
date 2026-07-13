"""Secret redaction helpers for trace and report payloads."""

from __future__ import annotations

import re

_SECRET_KEY_PATTERN = re.compile(
    r"(password|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|authorization)",
    re.IGNORECASE,
)

_REDACTED = "[REDACTED]"


def is_secret_like_key(key: str) -> bool:
    normalized = key.replace("-", "_").replace(" ", "_")
    return bool(_SECRET_KEY_PATTERN.search(normalized))


def reject_secret_metadata_keys(metadata: dict[str, str]) -> dict[str, str]:
    for key in metadata:
        if is_secret_like_key(key):
            raise ValueError(f"secret-like metadata key not allowed: {key}")
    return metadata


def redact_string(value: str) -> str:
    if not value:
        return value
    if any(token in value.lower() for token in ("password=", "secret=", "token=", "api_key=")):
        return _REDACTED
    return value


def redact_metadata(metadata: dict[str, str]) -> dict[str, str]:
    return {key: (_REDACTED if is_secret_like_key(key) else redact_string(value)) for key, value in metadata.items()}
