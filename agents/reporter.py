from models.report import ReportModel, WorkflowHistory


class Reporter:
    def run(self, history: WorkflowHistory) -> ReportModel:
        analysis = history.analysis
        if analysis is None:
            paper_title = "Unknown paper"
            goal_summary = "No reproduction goal recorded."
            evaluation_summary = "No evaluation criteria recorded."
        else:
            paper_title = analysis.metadata.title
            goal_summary = analysis.goal.research_goal or analysis.goal.target_experiment
            metric_names = [
                metric.name for metric in analysis.evaluation.metrics if metric.name
            ]
            evaluation_summary = ", ".join(metric_names) if metric_names else (
                analysis.evaluation.evaluation_protocol or "No evaluation metrics recorded."
            )

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
                f"Reproduced paper '{paper_title}'. Goal: {goal_summary}. "
                f"Evaluation focus: {evaluation_summary}."
            ),
            implementation_summary=(
                f"Generated workspace at {workspace_path} with {task_count} planned tasks."
            ),
            execution_history=history.execution_results,
            debugging_history=history.patch_plans,
            final_status=final_status,
        )
