import json
import re
import sys

from llm.coder_mock_provider import CoderMockLLMProvider
from llm.provider import LLMMessage, LLMProvider
from models.paper import PaperModel
from models.review import PatchPlan
from models.routing import RepositoryTarget, TaskRoutingTable
from models.task import TaskModel, TaskStep
from models.workspace import Workspace
from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader
from routing.task_router import TaskRouter
from workspace.manager import WorkspaceManager

_CATEGORY_ORDER = {
    "dependencies": 0,
    "source": 1,
    "config": 2,
    "script": 3,
}


class Coder:
    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        llm: LLMProvider | None = None,
        task_router: TaskRouter | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._workspace_manager = workspace_manager
        self._llm = llm or CoderMockLLMProvider()
        self._task_router = task_router or TaskRouter()
        self._prompt_builder = prompt_builder or PromptBuilder(PromptLoader())

    def run(
        self,
        paper: PaperModel,
        task: TaskModel,
        patch_plan: PatchPlan | None = None,
    ) -> Workspace:
        slug = self._paper_slug(paper.title)
        workspace = self._workspace_manager.create_workspace(slug)
        routing_table = self._task_router.route_task(task)
        self._workspace_manager.store_routing_table(workspace, routing_table)
        self._workspace_manager.initialize_repository(
            workspace,
            paper.title,
            task,
            patch_plan,
        )
        shared_generation_context = self._build_shared_generation_context(
            paper,
            task,
            routing_table,
        )
        populated_paths = self._populate_repository(
            workspace,
            task,
            routing_table,
            shared_generation_context,
        )
        self._finalize_readme(
            workspace,
            paper.title,
            task,
            patch_plan,
            shared_generation_context,
            populated_paths,
        )
        return workspace

    @staticmethod
    def _build_shared_generation_context(
        paper: PaperModel,
        task: TaskModel,
        routing_table: TaskRoutingTable,
    ) -> dict[str, object]:
        targets = routing_table.targets
        return {
            "paper_title": paper.title,
            "framework": paper.framework,
            "dataset": paper.dataset,
            "model": paper.model,
            "optimizer": paper.optimizer,
            "loss": paper.loss,
            "training_pipeline": paper.training_pipeline,
            "evaluation_metric": paper.evaluation_metric,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "repository_files": [target.relative_path for target in targets],
            "source_modules": [
                target.relative_path.removesuffix(".py").replace("/", ".")
                for target in targets
                if target.file_category == "source"
            ],
            "config_files": [
                target.relative_path
                for target in targets
                if target.file_category == "config"
            ],
            "script_files": [
                target.relative_path
                for target in targets
                if target.file_category == "script"
            ],
            "train_entrypoint": "scripts/train.py",
            "eval_entrypoint": "scripts/evaluate.py",
            "engineering_tasks": [
                {"id": step.id, "name": step.name, "description": step.description}
                for step in task.steps
            ],
        }

    def _populate_repository(
        self,
        workspace: Workspace,
        task: TaskModel,
        routing_table: TaskRoutingTable,
        shared_generation_context: dict[str, object],
    ) -> list[str]:
        populated_paths: list[str] = []
        for target in self._sort_targets(routing_table.targets):
            task_step = self._find_task_step(task, target.task_id)
            repository_context = self._format_repository_context(populated_paths)
            system_prompt = self._prompt_builder.build_coder_prompt(target.file_category)
            user_prompt = self._format_generation_request(
                shared_generation_context,
                task_step,
                target,
                repository_context,
            )
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
            content = self._llm.complete(messages, temperature=0.0)
            self._workspace_manager.write_file(workspace, target.relative_path, content)
            populated_paths.append(target.relative_path)
        return populated_paths

    def _finalize_readme(
        self,
        workspace: Workspace,
        paper_title: str,
        task: TaskModel,
        patch_plan: PatchPlan | None,
        shared_generation_context: dict[str, object],
        populated_paths: list[str],
    ) -> None:
        readme_content = self._format_populated_readme(
            paper_title,
            task,
            patch_plan,
            shared_generation_context,
            populated_paths,
        )
        self._workspace_manager.write_file(workspace, "README.md", readme_content)

    @staticmethod
    def _sort_targets(targets: list[RepositoryTarget]) -> list[RepositoryTarget]:
        return sorted(
            targets,
            key=lambda target: (
                _CATEGORY_ORDER.get(target.file_category, 99),
                target.relative_path,
            ),
        )

    @staticmethod
    def _find_task_step(task: TaskModel, task_id: str) -> TaskStep:
        for step in task.steps:
            if step.id == task_id:
                return step
        raise ValueError(f"Task step not found for routing target: {task_id}")

    @staticmethod
    def _format_repository_context(populated_paths: list[str]) -> str:
        if not populated_paths:
            return "No repository files generated yet."
        lines = ["Existing repository files:"]
        lines.extend(f"- {path}" for path in populated_paths)
        return "\n".join(lines)

    @staticmethod
    def _format_shared_generation_context(context: dict[str, object]) -> str:
        return json.dumps(context, indent=2, sort_keys=True)

    @staticmethod
    def _format_generation_request(
        shared_generation_context: dict[str, object],
        task_step: TaskStep,
        target: RepositoryTarget,
        repository_context: str,
    ) -> str:
        return "\n".join(
            [
                "Shared generation context:",
                Coder._format_shared_generation_context(shared_generation_context),
                "",
                f"Engineering task: {task_step.id} - {task_step.name}",
                f"Task description: {task_step.description}",
                f"Target file: {target.relative_path}",
                f"File category: {target.file_category}",
                "Repository context:",
                repository_context,
                "",
                "Generate this file to be consistent with the shared generation context.",
                "Use the same framework, dataset, model, and optimizer throughout.",
                "Scripts must only import from source modules listed in the context.",
                "requirements.txt must include packages imported across the repository.",
                "Configuration files must match the fields expected by scripts.",
            ]
        )

    @staticmethod
    def _format_populated_readme(
        paper_title: str,
        task: TaskModel,
        patch_plan: PatchPlan | None,
        shared_generation_context: dict[str, object],
        populated_paths: list[str],
    ) -> str:
        lines = [
            f"# {paper_title}",
            "",
            "## Reproduction Context",
            "",
            f"- **Framework:** {shared_generation_context['framework']}",
            f"- **Dataset:** {shared_generation_context['dataset']}",
            f"- **Model:** {shared_generation_context['model']}",
            f"- **Optimizer:** {shared_generation_context['optimizer']}",
            f"- **Python version:** {shared_generation_context['python_version']}",
            "",
            "## Project Structure",
            "",
            "```text",
            ".",
            "├── src/",
            "├── configs/",
            "├── scripts/",
            "├── outputs/",
            "├── logs/",
            "├── README.md",
            "└── requirements.txt",
            "```",
            "",
            "## Generated Files",
            "",
        ]
        if populated_paths:
            lines.extend(f"- `{path}`" for path in populated_paths)
        else:
            lines.append("- No implementation files generated.")
        lines.extend(
            [
                "",
                "## Engineering Tasks",
                "",
            ]
        )
        for step in task.steps:
            lines.append(
                f"- **{step.id}** ({step.status}): {step.name} — {step.description}"
            )
        if not task.steps:
            lines.append("- No tasks defined.")
        lines.extend(
            [
                "",
                "## Workspace Status",
                "",
                "- **Repository skeleton:** created",
                "- **Source code generation:** complete",
                "- **Configuration generation:** complete",
                "",
                "This workspace contains generated implementation files.",
            ]
        )
        if patch_plan is not None:
            lines.extend(
                [
                    "",
                    "## Patch Planning",
                    "",
                    patch_plan.reason,
                ]
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _paper_slug(title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        return slug or "paper"
