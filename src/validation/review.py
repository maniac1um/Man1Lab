from models.review_report import ReviewReport
from validation.exceptions import ReviewValidationError

_REQUIRED_STRING_FIELDS = ("summary", "analysis", "risk_level", "next_action")
_LIST_FIELDS = ("identified_issues", "strengths")
_ALLOWED_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}


def normalize_review_dict(data: dict) -> dict:
    normalized = {
        field: _require_non_empty_string(data, field) for field in _REQUIRED_STRING_FIELDS
    }
    normalized["risk_level"] = _normalize_risk_level(normalized["risk_level"])
    for field in _LIST_FIELDS:
        normalized[field] = _normalize_string_list(data, field)
    return normalized


def validate_review_dict(data: dict) -> None:
    for field in _REQUIRED_STRING_FIELDS:
        if field not in data:
            raise ReviewValidationError(f"Missing required field: {field}")
        _require_non_empty_string(data, field)

    for field in _LIST_FIELDS:
        if field not in data:
            raise ReviewValidationError(f"Missing required field: {field}")
        _normalize_string_list(data, field)

    risk_level = _normalize_risk_level(_require_non_empty_string(data, "risk_level"))
    if risk_level not in _ALLOWED_RISK_LEVELS:
        raise ReviewValidationError(f"Invalid risk_level: {data['risk_level']}")


def build_review_report(data: dict) -> ReviewReport:
    validate_review_dict(data)
    normalized = normalize_review_dict(data)
    return ReviewReport(**normalized)


def _require_non_empty_string(data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ReviewValidationError(f"Invalid required field: {field}")
    return value.strip()


def _normalize_string_list(data: dict, field: str) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list):
        raise ReviewValidationError(f"Invalid field: {field} must be a list")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ReviewValidationError(
                f"Invalid entry in {field} at index {index}"
            )
        normalized.append(item.strip())
    return normalized


def _normalize_risk_level(value: str) -> str:
    return value.strip().upper()
