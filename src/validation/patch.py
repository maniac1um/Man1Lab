from models.review import PatchPlan
from validation.exceptions import PatchValidationError

_REQUIRED_STRING_FIELDS = ("priority", "reason", "strategy")
_ALLOWED_PRIORITIES = {"LOW", "MEDIUM", "HIGH"}


def normalize_patch_dict(data: dict) -> dict:
    normalized = {
        "requires_patch": _normalize_bool(data, "requires_patch"),
        "priority": _normalize_priority(_require_non_empty_string(data, "priority")),
        "targets": _normalize_targets(data),
        "reason": _require_non_empty_string(data, "reason"),
        "strategy": _require_non_empty_string(data, "strategy"),
    }
    return normalized


def validate_patch_dict(data: dict) -> None:
    if "requires_patch" not in data:
        raise PatchValidationError("Missing required field: requires_patch")
    _normalize_bool(data, "requires_patch")

    for field in _REQUIRED_STRING_FIELDS:
        if field not in data:
            raise PatchValidationError(f"Missing required field: {field}")
        _require_non_empty_string(data, field)

    if "targets" not in data:
        raise PatchValidationError("Missing required field: targets")
    _normalize_targets(data)

    priority = _normalize_priority(_require_non_empty_string(data, "priority"))
    if priority not in _ALLOWED_PRIORITIES:
        raise PatchValidationError(f"Invalid priority: {data['priority']}")


def build_patch_plan(data: dict) -> PatchPlan:
    validate_patch_dict(data)
    normalized = normalize_patch_dict(data)
    return PatchPlan(**normalized)


def _normalize_bool(data: dict, field: str) -> bool:
    value = data.get(field)
    if not isinstance(value, bool):
        raise PatchValidationError(f"Invalid required field: {field}")
    return value


def _require_non_empty_string(data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PatchValidationError(f"Invalid required field: {field}")
    return value.strip()


def _normalize_priority(value: str) -> str:
    return value.strip().upper()


def _normalize_targets(data: dict) -> list[str]:
    value = data.get("targets")
    if not isinstance(value, list):
        raise PatchValidationError("Invalid field: targets must be a list")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise PatchValidationError(f"Invalid entry in targets at index {index}")
        normalized.append(item.strip())
    return normalized
