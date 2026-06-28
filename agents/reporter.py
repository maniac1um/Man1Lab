from models.report import ReportModel, WorkflowHistory


class Reporter:
    def run(self, history: WorkflowHistory) -> ReportModel:
        paper_title = history.paper.title if history.paper else "Unknown paper"
        task_count = len(history.task.steps) if history.task else 0
        workspace_path = (
            str(history.workspace.root_path) if history.workspace else "N/A"
        )
        final_status = (
            "SUCCESS"
            if history.execution_results
            and history.execution_results[-1].exit_code == 0
            else "FAILED"
        )

        return ReportModel(
            reproduction_summary=(
                f"Reproduced paper '{paper_title}' through the autonomous workflow."
            ),
            implementation_summary=(
                f"Generated workspace at {workspace_path} with {task_count} planned tasks."
            ),
            execution_history=history.execution_results,
            debugging_history=history.patch_plans,
            final_status=final_status,
        )
