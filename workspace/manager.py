import re
from datetime import datetime
from pathlib import Path

import config
from models.report import ReportModel
from models.workspace import Workspace


class WorkspaceManager:
    def __init__(self, root: Path | None = None, outputs_dir: Path | None = None) -> None:
        self._root = root or config.WORKSPACE_ROOT
        self._outputs_dir = outputs_dir or config.OUTPUTS_DIR
        self._root.mkdir(parents=True, exist_ok=True)
        self._outputs_dir.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, paper_slug: str) -> Workspace:
        slug = self._sanitize_slug(paper_slug)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        workspace_name = f"{timestamp}_{slug}"
        root_path = self._root / workspace_name
        for subdir in ("src", "configs", "scripts", "logs", "outputs"):
            (root_path / subdir).mkdir(parents=True, exist_ok=True)
        return Workspace(root_path=root_path, paper_slug=slug)

    def write_file(self, workspace: Workspace, relative_path: str, content: str) -> None:
        path = workspace.root_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def read_file(self, workspace: Workspace, relative_path: str) -> str:
        path = workspace.root_path / relative_path
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return path.read_text(encoding="utf-8")

    def write_output(self, workspace: Workspace, relative_path: str, content: str) -> Path:
        output_path = workspace.root_path / "outputs" / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def write_report(self, report: ReportModel, filename: str = "report.md") -> Path:
        report_path = self._outputs_dir / filename
        report_path.write_text(self._format_report(report), encoding="utf-8")
        return report_path

    @staticmethod
    def _sanitize_slug(paper_slug: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", paper_slug.lower()).strip("_")
        return slug or "paper"

    @staticmethod
    def _format_report(report: ReportModel) -> str:
        lines = [
            "# ResearchAgent Reproduction Report",
            "",
            "## Reproduction Summary",
            report.reproduction_summary,
            "",
            "## Implementation Summary",
            report.implementation_summary,
            "",
            "## Final Status",
            report.final_status,
            "",
            "## Execution History",
        ]
        for index, result in enumerate(report.execution_history, start=1):
            lines.extend(
                [
                    f"### Run {index}",
                    f"- Command: `{result.executed_command}`",
                    f"- Exit code: {result.exit_code}",
                    f"- Duration: {result.execution_time_seconds:.2f}s",
                    "",
                ]
            )
        lines.append("## Debugging History")
        for index, patch in enumerate(report.debugging_history, start=1):
            lines.extend(
                [
                    f"### Review {index}",
                    f"- Requires patch: {patch.requires_patch}",
                    f"- Analysis: {patch.analysis}",
                    "",
                ]
            )
        return "\n".join(lines)
