"""Versioned deterministic task templates."""

from __future__ import annotations

from dataclasses import dataclass

from execution_materialization.ports import ResolvedReference
from models.execution_graph import ExecutionGraphStageType
from models.execution_materialization import ExecutableTaskSpec, MaterializationIssue, MaterializationIssueSeverity


@dataclass(frozen=True)
class TaskTemplate:
    template_id: str
    template_version: str
    supported_stages: frozenset[ExecutionGraphStageType]
    required_evidence: frozenset[str]


@dataclass(frozen=True)
class TemplateResolution:
    template: TaskTemplate | None
    issue: MaterializationIssue | None = None


class TaskTemplateRegistry:
    """Resolve versioned templates without guessing commands."""

    def __init__(self, templates: tuple[TaskTemplate, ...] | None = None) -> None:
        self._templates = templates or default_templates()
        self._by_stage: dict[ExecutionGraphStageType, TaskTemplate] = {}
        for template in self._templates:
            for stage in template.supported_stages:
                self._by_stage[stage] = template

    def resolve(self, stage_type: ExecutionGraphStageType) -> TemplateResolution:
        template = self._by_stage.get(stage_type)
        if template is None:
            return TemplateResolution(
                template=None,
                issue=MaterializationIssue(
                    code="unsupported_stage",
                    message=f"no supported template for stage {stage_type.value}",
                    severity=MaterializationIssueSeverity.ERROR,
                    stage_type=stage_type.value,
                ),
            )
        return TemplateResolution(template=template)


def default_templates() -> tuple[TaskTemplate, ...]:
    return (
        TaskTemplate(
            template_id="local/pip_install_requirements",
            template_version="1.0",
            supported_stages=frozenset({ExecutionGraphStageType.PREPARE_ENVIRONMENT}),
            required_evidence=frozenset({"requirements_file", "prepared_repo_path"}),
        ),
        TaskTemplate(
            template_id="local/python_train_script",
            template_version="1.0",
            supported_stages=frozenset({ExecutionGraphStageType.TRAINING}),
            required_evidence=frozenset(
                {"prepared_repo_path", "entry_script", "config_path", "output_path"}
            ),
        ),
        TaskTemplate(
            template_id="local/python_eval_script",
            template_version="1.0",
            supported_stages=frozenset({ExecutionGraphStageType.EVALUATION}),
            required_evidence=frozenset(
                {"prepared_repo_path", "eval_script", "config_path", "output_path"}
            ),
        ),
        TaskTemplate(
            template_id="local/report_collect",
            template_version="1.0",
            supported_stages=frozenset({ExecutionGraphStageType.COMPARISON}),
            required_evidence=frozenset(
                {"prepared_repo_path", "comparison_script", "output_path"}
            ),
        ),
    )


def _path_relative_to_workdir(repo_path: str, path_text: str) -> str:
    normalized = path_text.replace("\\", "/").strip()
    repo_prefix = repo_path.replace("\\", "/").strip().rstrip("/")
    if normalized.startswith(f"{repo_prefix}/"):
        return normalized[len(repo_prefix) + 1 :]
    return normalized


def build_spec_from_template(
    *,
    template: TaskTemplate,
    stage_type: ExecutionGraphStageType,
    working_directory: str,
    evidence: dict[str, ResolvedReference],
    binding_ids: tuple[str, ...],
    asset_ids: tuple[str, ...],
    environment_variables: dict[str, str] | None = None,
    timeout_seconds: float | None = None,
) -> ExecutableTaskSpec | MaterializationIssue:
    missing = sorted(key for key in template.required_evidence if key not in evidence)
    if missing:
        return MaterializationIssue(
            code="missing_evidence",
            message=f"missing verified evidence: {', '.join(missing)}",
            severity=MaterializationIssueSeverity.ERROR,
            stage_type=stage_type.value,
            template_id=template.template_id,
        )

    repo = evidence["prepared_repo_path"].path
    workdir = repo

    if template.template_id == "local/pip_install_requirements":
        requirements = _path_relative_to_workdir(repo, evidence["requirements_file"].path)
        command = ("python", "-m", "pip", "install", "-r", requirements)
        return ExecutableTaskSpec(
            command=command,
            working_directory=workdir,
            environment_variables=dict(environment_variables or {}),
            timeout_seconds=timeout_seconds,
            artifact_paths={"environment": requirements},
            template_id=template.template_id,
            template_version=template.template_version,
            source_binding_ids=binding_ids,
            source_asset_ids=asset_ids,
            provenance="materialization:template:pip_install_requirements",
        )

    if template.template_id == "local/python_train_script":
        entry = _path_relative_to_workdir(repo, evidence["entry_script"].path)
        config = _path_relative_to_workdir(repo, evidence["config_path"].path)
        output = _path_relative_to_workdir(repo, evidence["output_path"].path)
        command = ("python", entry, "--config", config)
        return ExecutableTaskSpec(
            command=command,
            working_directory=workdir,
            environment_variables=dict(environment_variables or {}),
            timeout_seconds=timeout_seconds or 86400.0,
            artifact_paths={"training_output": output},
            template_id=template.template_id,
            template_version=template.template_version,
            source_binding_ids=binding_ids,
            source_asset_ids=asset_ids,
            provenance="materialization:template:python_train_script",
        )

    if template.template_id == "local/python_eval_script":
        entry = _path_relative_to_workdir(repo, evidence["eval_script"].path)
        config = _path_relative_to_workdir(repo, evidence["config_path"].path)
        output = _path_relative_to_workdir(repo, evidence["output_path"].path)
        command = ("python", entry, "--config", config)
        return ExecutableTaskSpec(
            command=command,
            working_directory=workdir,
            environment_variables=dict(environment_variables or {}),
            timeout_seconds=timeout_seconds or 3600.0,
            artifact_paths={"evaluation_output": output},
            template_id=template.template_id,
            template_version=template.template_version,
            source_binding_ids=binding_ids,
            source_asset_ids=asset_ids,
            provenance="materialization:template:python_eval_script",
        )

    if template.template_id == "local/report_collect":
        entry = _path_relative_to_workdir(repo, evidence["comparison_script"].path)
        output = _path_relative_to_workdir(repo, evidence["output_path"].path)
        command = ("python", entry, "--output", output)
        return ExecutableTaskSpec(
            command=command,
            working_directory=workdir,
            environment_variables=dict(environment_variables or {}),
            timeout_seconds=timeout_seconds or 300.0,
            artifact_paths={"report": output},
            template_id=template.template_id,
            template_version=template.template_version,
            source_binding_ids=binding_ids,
            source_asset_ids=asset_ids,
            provenance="materialization:template:report_collect",
        )

    return MaterializationIssue(
        code="unsupported_template",
        message=f"template builder missing for {template.template_id}",
        severity=MaterializationIssueSeverity.ERROR,
        stage_type=stage_type.value,
        template_id=template.template_id,
    )
