from pathlib import Path

from models.paper_reproduction_analysis import (
    SCHEMA_VERSION,
    AnalysisEvaluation,
    AnalysisGoal,
    AnalysisMethod,
    AnalysisResources,
    ArtifactReference,
    ArtifactType,
    BaselineSpec,
    DatasetResource,
    DependencyResource,
    ExternalResource,
    GapCategory,
    Hyperparameter,
    MetricSpec,
    ModelResource,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionGap,
    ReproductionScope,
)
from validation.exceptions import AnalysisValidationError

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


def validate_analysis_dict(data: dict) -> None:
    if not isinstance(data, dict):
        raise AnalysisValidationError("Analysis data must be a dict")

    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        raise AnalysisValidationError("Missing required field: metadata")

    _require_non_empty_string(metadata, "title", path="metadata")

    goal = data.get("goal")
    if not isinstance(goal, dict):
        raise AnalysisValidationError("Missing required field: goal")

    _require_non_empty_string(goal, "research_goal", path="goal")
    _validate_scope(goal.get("scope"), path="goal.scope")

    resources = data.get("resources", {})
    if resources is not None and not isinstance(resources, dict):
        raise AnalysisValidationError("Invalid field: resources must be a dict")

    method = data.get("method", {})
    if method is not None and not isinstance(method, dict):
        raise AnalysisValidationError("Invalid field: method must be a dict")

    evaluation = data.get("evaluation", {})
    if evaluation is not None and not isinstance(evaluation, dict):
        raise AnalysisValidationError("Invalid field: evaluation must be a dict")

    gaps = data.get("reproduction_gaps", [])
    if gaps is not None and not isinstance(gaps, list):
        raise AnalysisValidationError("Invalid field: reproduction_gaps must be a list")

    if isinstance(resources, dict):
        _validate_resource_lists(resources)

    if isinstance(method, dict):
        _validate_hyperparameter_list(method.get("hyperparameters", []), "method.hyperparameters")

    if isinstance(evaluation, dict):
        _validate_metric_list(evaluation.get("metrics", []), "evaluation.metrics")
        _validate_baseline_list(evaluation.get("baselines", []), "evaluation.baselines")

    if isinstance(gaps, list):
        _validate_gap_list(gaps)


def normalize_analysis_dict(data: dict) -> dict:
    metadata = _normalize_metadata(data.get("metadata", {}))
    goal = _normalize_goal(data.get("goal", {}))
    resources = _normalize_resources(data.get("resources", {}))
    method = _normalize_method(data.get("method", {}))
    evaluation = _normalize_evaluation(data.get("evaluation", {}))
    reproduction_gaps = _normalize_gap_list(data.get("reproduction_gaps", []))
    schema_version = _normalize_optional_string(data.get("schema_version"), SCHEMA_VERSION)

    return {
        "schema_version": schema_version or SCHEMA_VERSION,
        "metadata": metadata,
        "goal": goal,
        "resources": resources,
        "method": method,
        "evaluation": evaluation,
        "reproduction_gaps": reproduction_gaps,
    }


def build_paper_reproduction_analysis(
    data: dict,
    source_path: Path | None = None,
) -> PaperReproductionAnalysis:
    validate_analysis_dict(data)
    normalized = normalize_analysis_dict(data)
    if source_path is not None:
        metadata = dict(normalized["metadata"])
        metadata["source_path"] = source_path
        normalized["metadata"] = metadata
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(**normalized["metadata"]),
        goal=AnalysisGoal(**normalized["goal"]),
        resources=AnalysisResources(**normalized["resources"]),
        method=AnalysisMethod(**normalized["method"]),
        evaluation=AnalysisEvaluation(**normalized["evaluation"]),
        reproduction_gaps=[
            ReproductionGap(**gap) for gap in normalized["reproduction_gaps"]
        ],
        schema_version=normalized["schema_version"],
    )


def _normalize_metadata(data: dict) -> dict:
    if not isinstance(data, dict):
        raise AnalysisValidationError("Invalid field: metadata must be a dict")

    authors = data.get("authors", [])
    if authors is None:
        authors = []
    if not isinstance(authors, list):
        raise AnalysisValidationError("Invalid field: metadata.authors must be a list")

    year = data.get("year")
    if year is not None and not isinstance(year, int):
        raise AnalysisValidationError("Invalid field: metadata.year must be an integer")

    return {
        "title": _require_non_empty_string(data, "title", path="metadata"),
        "authors": [_normalize_optional_string(item) for item in authors if item is not None],
        "venue": _normalize_optional_string(data.get("venue")),
        "year": year,
        "arxiv_id": _normalize_optional_string(data.get("arxiv_id")),
    }


def _normalize_goal(data: dict) -> dict:
    if not isinstance(data, dict):
        raise AnalysisValidationError("Invalid field: goal must be a dict")

    scope = _normalize_scope(data.get("scope"))

    return {
        "scope": scope,
        "research_goal": _require_non_empty_string(data, "research_goal", path="goal"),
        "target_experiment": _normalize_optional_string(data.get("target_experiment")),
        "expected_outcome": _normalize_optional_string(data.get("expected_outcome")),
    }


def _normalize_resources(data: dict) -> dict:
    if not isinstance(data, dict):
        raise AnalysisValidationError("Invalid field: resources must be a dict")

    return {
        "datasets": _normalize_dataset_list(data.get("datasets", [])),
        "models": _normalize_model_list(data.get("models", [])),
        "dependencies": _normalize_dependency_list(data.get("dependencies", [])),
        "external_resources": _normalize_external_resource_list(
            data.get("external_resources", [])
        ),
        "artifacts": _normalize_artifact_list(data.get("artifacts", [])),
    }


def _normalize_method(data: dict) -> dict:
    if not isinstance(data, dict):
        raise AnalysisValidationError("Invalid field: method must be a dict")

    framework = _normalize_alias(
        _normalize_optional_string(data.get("framework")),
        _FRAMEWORK_ALIASES,
    )
    optimizer = _normalize_alias(
        _normalize_optional_string(data.get("optimizer")),
        _OPTIMIZER_ALIASES,
    )

    return {
        "framework": framework,
        "architecture": _normalize_optional_string(data.get("architecture")),
        "training_pipeline": _normalize_optional_string(data.get("training_pipeline")),
        "optimizer": optimizer,
        "loss": _normalize_optional_string(data.get("loss")),
        "hyperparameters": _normalize_hyperparameter_list(data.get("hyperparameters", [])),
        "data_processing": _normalize_optional_string(data.get("data_processing")),
    }


def _normalize_evaluation(data: dict) -> dict:
    if not isinstance(data, dict):
        raise AnalysisValidationError("Invalid field: evaluation must be a dict")

    benchmarks = data.get("benchmarks", [])
    if benchmarks is None:
        benchmarks = []
    if not isinstance(benchmarks, list):
        raise AnalysisValidationError("Invalid field: evaluation.benchmarks must be a list")

    return {
        "metrics": _normalize_metric_list(data.get("metrics", [])),
        "benchmarks": [
            _normalize_optional_string(item)
            for item in benchmarks
            if _normalize_optional_string(item)
        ],
        "evaluation_protocol": _normalize_optional_string(
            data.get("evaluation_protocol")
        ),
        "baselines": _normalize_baseline_list(data.get("baselines", [])),
    }


def _normalize_dataset_list(items: list | None) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise AnalysisValidationError("Invalid field: resources.datasets must be a list")

    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid dataset at index {index}")
        normalized.append(
            {
                "name": _require_non_empty_string(item, "name", path=f"resources.datasets[{index}]"),
                "description": _normalize_optional_string(item.get("description")),
                "link": _normalize_optional_string(item.get("link")),
                "split_or_variant": _normalize_optional_string(item.get("split_or_variant")),
            }
        )
    return normalized


def _normalize_model_list(items: list | None) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise AnalysisValidationError("Invalid field: resources.models must be a list")

    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid model resource at index {index}")
        normalized.append(
            {
                "name": _require_non_empty_string(item, "name", path=f"resources.models[{index}]"),
                "description": _normalize_optional_string(item.get("description")),
                "role": _normalize_optional_string(item.get("role")),
            }
        )
    return normalized


def _normalize_dependency_list(items: list | None) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise AnalysisValidationError("Invalid field: resources.dependencies must be a list")

    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid dependency at index {index}")
        normalized.append(
            {
                "name": _require_non_empty_string(
                    item, "name", path=f"resources.dependencies[{index}]"
                ),
                "version": _normalize_optional_string(item.get("version")),
                "purpose": _normalize_optional_string(item.get("purpose")),
            }
        )
    return normalized


def _normalize_external_resource_list(items: list | None) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise AnalysisValidationError(
            "Invalid field: resources.external_resources must be a list"
        )

    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid external resource at index {index}")
        normalized.append(
            {
                "resource_type": _require_non_empty_string(
                    item,
                    "resource_type",
                    path=f"resources.external_resources[{index}]",
                ),
                "name": _require_non_empty_string(
                    item, "name", path=f"resources.external_resources[{index}]"
                ),
                "url": _normalize_optional_string(item.get("url")),
                "notes": _normalize_optional_string(item.get("notes")),
            }
        )
    return normalized


def _normalize_artifact_list(items: list | None) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise AnalysisValidationError("Invalid field: resources.artifacts must be a list")

    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid artifact at index {index}")
        normalized.append(
            {
                "artifact_type": _normalize_artifact_type(
                    item.get("artifact_type"),
                    path=f"resources.artifacts[{index}].artifact_type",
                ),
                "name": _require_non_empty_string(
                    item, "name", path=f"resources.artifacts[{index}]"
                ),
                "location": _normalize_optional_string(item.get("location")),
                "notes": _normalize_optional_string(item.get("notes")),
            }
        )
    return normalized


def _normalize_hyperparameter_list(items: list | None) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise AnalysisValidationError("Invalid field: method.hyperparameters must be a list")

    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid hyperparameter at index {index}")
        normalized.append(
            {
                "name": _require_non_empty_string(
                    item, "name", path=f"method.hyperparameters[{index}]"
                ),
                "value": _normalize_optional_string(item.get("value")),
                "notes": _normalize_optional_string(item.get("notes")),
            }
        )
    return normalized


def _normalize_metric_list(items: list | None) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise AnalysisValidationError("Invalid field: evaluation.metrics must be a list")

    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid metric at index {index}")
        normalized.append(
            {
                "name": _require_non_empty_string(
                    item, "name", path=f"evaluation.metrics[{index}]"
                ),
                "definition": _normalize_optional_string(item.get("definition")),
                "reported_value": _normalize_optional_string(item.get("reported_value")),
            }
        )
    return normalized


def _normalize_baseline_list(items: list | None) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise AnalysisValidationError("Invalid field: evaluation.baselines must be a list")

    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid baseline at index {index}")
        normalized.append(
            {
                "name": _require_non_empty_string(
                    item, "name", path=f"evaluation.baselines[{index}]"
                ),
                "description": _normalize_optional_string(item.get("description")),
            }
        )
    return normalized


def _normalize_gap_list(items: list | None) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise AnalysisValidationError("Invalid field: reproduction_gaps must be a list")

    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid reproduction gap at index {index}")
        normalized.append(
            {
                "category": _normalize_gap_category(
                    item.get("category"),
                    path=f"reproduction_gaps[{index}].category",
                ),
                "description": _require_non_empty_string(
                    item, "description", path=f"reproduction_gaps[{index}]"
                ),
            }
        )
    return normalized


def _validate_resource_lists(resources: dict) -> None:
    _validate_named_list(resources.get("datasets", []), "resources.datasets", ("name",))
    _validate_named_list(resources.get("models", []), "resources.models", ("name",))
    _validate_named_list(resources.get("dependencies", []), "resources.dependencies", ("name",))
    _validate_named_list(
        resources.get("external_resources", []),
        "resources.external_resources",
        ("resource_type", "name"),
    )
    _validate_artifact_list(resources.get("artifacts", []))


def _validate_named_list(
    items: list | None,
    path: str,
    required_fields: tuple[str, ...],
) -> None:
    if items is None:
        return
    if not isinstance(items, list):
        raise AnalysisValidationError(f"Invalid field: {path} must be a list")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid item at {path}[{index}]")
        for field in required_fields:
            if field not in item:
                raise AnalysisValidationError(
                    f"Missing required field: {field} in {path}[{index}]"
                )
            _require_non_empty_string(item, field, path=f"{path}[{index}]")


def _validate_artifact_list(items: list | None) -> None:
    if items is None:
        return
    if not isinstance(items, list):
        raise AnalysisValidationError("Invalid field: resources.artifacts must be a list")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid artifact at index {index}")
        if "artifact_type" not in item:
            raise AnalysisValidationError(
                f"Missing required field: artifact_type in resources.artifacts[{index}]"
            )
        _normalize_artifact_type(
            item.get("artifact_type"),
            path=f"resources.artifacts[{index}].artifact_type",
        )
        _require_non_empty_string(item, "name", path=f"resources.artifacts[{index}]")


def _validate_hyperparameter_list(items: list | None, path: str) -> None:
    _validate_named_list(items, path, ("name",))


def _validate_metric_list(items: list | None, path: str) -> None:
    _validate_named_list(items, path, ("name",))


def _validate_baseline_list(items: list | None, path: str) -> None:
    _validate_named_list(items, path, ("name",))


def _validate_gap_list(items: list) -> None:
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Invalid reproduction gap at index {index}")
        if "category" not in item:
            raise AnalysisValidationError(
                f"Missing required field: category in reproduction_gaps[{index}]"
            )
        _normalize_gap_category(
            item.get("category"),
            path=f"reproduction_gaps[{index}].category",
        )
        _require_non_empty_string(item, "description", path=f"reproduction_gaps[{index}]")


def _normalize_scope(value: object) -> ReproductionScope:
    if value is None or value == "":
        return ReproductionScope.UNKNOWN
    if isinstance(value, ReproductionScope):
        return value
    if not isinstance(value, str):
        raise AnalysisValidationError("Invalid field: goal.scope must be a string")
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    for scope in ReproductionScope:
        if scope.value == normalized:
            return scope
    raise AnalysisValidationError(f"Invalid reproduction scope: {value!r}")


def _validate_scope(value: object, *, path: str) -> None:
    if value is None or value == "":
        return
    _normalize_scope(value)


def _normalize_artifact_type(value: object, *, path: str) -> ArtifactType:
    if isinstance(value, ArtifactType):
        return value
    if not isinstance(value, str) or not value.strip():
        raise AnalysisValidationError(f"Invalid field: {path}")
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    for artifact_type in ArtifactType:
        if artifact_type.value == normalized:
            return artifact_type
    raise AnalysisValidationError(f"Invalid artifact type: {value!r}")


def _normalize_gap_category(value: object, *, path: str) -> GapCategory:
    if isinstance(value, GapCategory):
        return value
    if not isinstance(value, str) or not value.strip():
        raise AnalysisValidationError(f"Invalid field: {path}")
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    for category in GapCategory:
        if category.value == normalized:
            return category
    raise AnalysisValidationError(f"Invalid gap category: {value!r}")


def _require_non_empty_string(data: dict, field: str, *, path: str) -> str:
    if field not in data:
        raise AnalysisValidationError(f"Missing required field: {path}.{field}")
    value = data[field]
    if not isinstance(value, str):
        raise AnalysisValidationError(f"Invalid required field: {path}.{field}")
    stripped = value.strip()
    if not stripped:
        raise AnalysisValidationError(f"Invalid required field: {path}.{field}")
    return stripped


def _normalize_optional_string(value: object, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        return str(value).strip()
    return value.strip()


def _normalize_alias(value: str, aliases: dict[str, str]) -> str:
    if not value:
        return value
    return aliases.get(value.casefold(), value)
