import re

from llm.provider import LLMProvider
from models.paper import PaperModel
from models.review import PatchPlan
from models.task import TaskModel
from models.workspace import Workspace
from workspace.manager import WorkspaceManager


class Coder:
    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        llm: LLMProvider | None = None,
    ) -> None:
        self._workspace_manager = workspace_manager
        self._llm = llm

    def run(
        self,
        paper: PaperModel,
        task: TaskModel,
        patch_plan: PatchPlan | None = None,
    ) -> Workspace:
        slug = self._paper_slug(paper.title)
        workspace = self._workspace_manager.create_workspace(slug)
        patch_note = ""
        if patch_plan is not None:
            patch_note = f"\n# Patch analysis\n{patch_plan.analysis}\n"

        self._workspace_manager.write_file(
            workspace,
            "README.md",
            f"# {paper.title}\n\nReproduction workspace for {task.paper_title}.\n{patch_note}",
        )
        self._workspace_manager.write_file(
            workspace,
            "src/main.py",
            '"""Mock entry point for reproduction project."""\n\n'
            'def main() -> None:\n'
            '    print("Training complete.")\n\n\n'
            'if __name__ == "__main__":\n'
            "    main()\n",
        )
        self._workspace_manager.write_file(
            workspace,
            "scripts/train.py",
            'from src.main import main\n\nif __name__ == "__main__":\n    main()\n',
        )
        return workspace

    @staticmethod
    def _paper_slug(title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        return slug or "paper"
