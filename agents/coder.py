import re

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
        self._populate_repository(workspace, paper, task, routing_table)
        return workspace

    def _populate_repository(
        self,
        workspace: Workspace,
        paper: PaperModel,
        task: TaskModel,
        routing_table: TaskRoutingTable,
    ) -> None:
        populated_paths: list[str] = []
        for target in routing_table.targets:
            task_step = self._find_task_step(task, target.task_id)
            repository_context = self._format_repository_context(populated_paths)
            system_prompt = self._prompt_builder.build_coder_prompt(target.file_category)
            user_prompt = self._format_generation_request(
                paper.title,
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
    def _format_generation_request(
        paper_title: str,
        task_step: TaskStep,
        target: RepositoryTarget,
        repository_context: str,
    ) -> str:
        return "\n".join(
            [
                f"Paper title: {paper_title}",
                f"Engineering task: {task_step.id} - {task_step.name}",
                f"Task description: {task_step.description}",
                f"Target file: {target.relative_path}",
                f"File category: {target.file_category}",
                "Repository context:",
                repository_context,
            ]
        )

    @staticmethod
    def _paper_slug(title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        return slug or "paper"
