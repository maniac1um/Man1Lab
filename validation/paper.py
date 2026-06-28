from pathlib import Path

from models.paper import PaperModel
from validation.exceptions import PaperValidationError

_REQUIRED_FIELD = "title"
_OPTIONAL_FIELDS = (
    "abstract",
    "method",
    "dataset",
    "model",
    "framework",
    "optimizer",
    "loss",
    "training_pipeline",
    "evaluation_metric",
)

_FRAMEWORK_ALIASES = {
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "jax": "JAX",
}

_OPTIMIZER_ALIASES = {
    "adam": "Adam",
    "adamw": "AdamW",
    "sgd": "SGD",
    "rmsprop": "RMSprop",
}


def normalize_paper_dict(data: dict) -> dict:
    normalized = {field: _normalize_optional_field(data, field) for field in _OPTIONAL_FIELDS}
    normalized[_REQUIRED_FIELD] = _normalize_required_field(data, _REQUIRED_FIELD)
    normalized["framework"] = _normalize_alias(
        normalized["framework"], _FRAMEWORK_ALIASES
    )
    normalized["optimizer"] = _normalize_alias(
        normalized["optimizer"], _OPTIMIZER_ALIASES
    )
    return normalized


def validate_paper_dict(data: dict) -> None:
    if _REQUIRED_FIELD not in data:
        raise PaperValidationError(f"Missing required field: {_REQUIRED_FIELD}")

    title = data[_REQUIRED_FIELD]
    if not isinstance(title, str) or not title.strip():
        raise PaperValidationError(f"Invalid required field: {_REQUIRED_FIELD}")


def build_paper_model(data: dict, source_path: Path) -> PaperModel:
    validate_paper_dict(data)
    normalized = normalize_paper_dict(data)
    return PaperModel(**normalized, source_path=source_path)


def _normalize_required_field(data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise PaperValidationError(f"Invalid required field: {field}")
    return value.strip()


def _normalize_optional_field(data: dict, field: str) -> str:
    value = data.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value).strip()
    return value.strip()


def _normalize_alias(value: str, aliases: dict[str, str]) -> str:
    if not value:
        return value
    return aliases.get(value.casefold(), value)
