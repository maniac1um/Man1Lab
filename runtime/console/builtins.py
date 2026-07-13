"""Built-in Man1Lab console commands."""

from __future__ import annotations

from pathlib import Path

from runtime.console.command import ConsoleCommand, ConsoleContext
from runtime.console.registry import CommandRegistry
from runtime.session.state import SessionState
from runtime.session.workspace_resume import (
    diagnose_for_discover,
    diagnose_for_execute,
    diagnose_for_plan,
    diagnose_for_plan_all,
    hydrate_workspace_from_disk,
    render_diagnostic,
)
from runtime.session.workspace_store import WorkspaceArtifactStore
from runtime.session.decision_artifacts import (
    persist_discovery_decision_artifacts,
    persist_planning_decision_artifacts,
)


def _format_check_status(status: str) -> str:
    return {"ok": "✓", "warn": "⚠", "fail": "✗"}.get(status, status)


def register_builtin_commands(registry: CommandRegistry) -> None:
    """Register the initial interactive console command set."""
    commands = (
        ConsoleCommand("help", "Show available commands and guided steps.", _cmd_help),
        ConsoleCommand("doctor", "Validate runtime environment.", _cmd_doctor),
        ConsoleCommand("profile", "Profile startup and runtime initialization.", _cmd_profile),
        ConsoleCommand("model", "Model profile commands (list, current, use).", _cmd_model),
        ConsoleCommand("clear", "Clear the console screen.", _cmd_clear),
        ConsoleCommand("exit", "Exit the console.", _cmd_exit),
        ConsoleCommand("analyze", "Analyze a paper PDF.", _cmd_analyze),
        ConsoleCommand("discover", "Run discovery for the current paper.", _cmd_discover),
        ConsoleCommand("plan", "Run execution planning for the current session.", _cmd_plan),
        ConsoleCommand("execute", "Run the planned execution graph.", _cmd_execute),
        ConsoleCommand(
            "execution",
            "Execution run commands (status, report).",
            _cmd_execution,
        ),
        ConsoleCommand(
            "plan-all",
            "Run analyze, discover, and plan for a paper.",
            _cmd_plan_all,
        ),
        ConsoleCommand(
            "execute-all",
            "Run the planned execution graph (alias for execute).",
            _cmd_execute_all,
        ),
        ConsoleCommand(
            "reproduce",
            "Run full reproduction pipeline (reserved).",
            _cmd_reproduce,
        ),
    )
    for command in commands:
        registry.register(command)


def _workspace_store(ctx: ConsoleContext) -> WorkspaceArtifactStore:
    root = ctx.platform.settings.workspace_root
    return WorkspaceArtifactStore(root)


def _cmd_help(ctx: ConsoleContext, _args: list[str]) -> int:
    ctx.renderer.render_help(ctx.registry)
    return 0


def _cmd_doctor(ctx: ConsoleContext, _args: list[str]) -> int:
    report = ctx.platform.doctor()
    llm_checks = [check for check in report.checks if check.name.startswith("LLM")]
    other_checks = [check for check in report.checks if not check.name.startswith("LLM")]
    for check in other_checks:
        symbol = _format_check_status(check.status)
        ctx.renderer.write(f"{symbol} {check.name}: {check.message}")
    if llm_checks:
        ctx.renderer.write("")
        ctx.renderer.write("LLM")
        for check in llm_checks:
            symbol = _format_check_status(check.status)
            label = check.name.removeprefix("LLM ").strip()
            ctx.renderer.write(f"{symbol} {label}: {check.message}")
    if report.healthy:
        ctx.renderer.write("Environment check passed.")
    else:
        ctx.renderer.write_error("Environment check failed.")
    return 0


def _cmd_profile(ctx: ConsoleContext, _args: list[str]) -> int:
    profile = ctx.platform.run_startup_profile()
    ctx.renderer.write(profile.format_report())
    return 0


def _cmd_model(ctx: ConsoleContext, args: list[str]) -> int:
    if not args or args[0] == "list":
        report = ctx.platform.list_models()
        for profile in report.profiles:
            marker = "*" if profile.active else " "
            enabled = "yes" if profile.enabled else "no"
            ctx.renderer.write(
                f"{marker} {profile.profile_name:<12} {profile.provider:<10} "
                f"{profile.model:<20} enabled={enabled}"
            )
        return 0
    if args[0] == "current":
        report = ctx.platform.current_model()
        if report is None:
            ctx.renderer.write_error("No active model profile is configured.")
            return 0
        ctx.renderer.write(f"Active Profile: {report.profile_name}")
        ctx.renderer.write(f"Provider: {report.provider}")
        ctx.renderer.write(f"Model: {report.model}")
        return 0
    if args[0] == "use" and len(args) >= 2:
        result = ctx.platform.use_model(args[1])
        if result.successful:
            ctx.renderer.write(result.message)
            ctx.renderer.write(f"Active profile: {result.active_profile}")
        else:
            ctx.renderer.write_error(result.message)
        return 0
    ctx.renderer.write_error("Usage: model [list|current|use <profile>]")
    return 0


def _cmd_clear(ctx: ConsoleContext, _args: list[str]) -> int:
    ctx.renderer.clear()
    return 0


def _cmd_exit(_ctx: ConsoleContext, _args: list[str]) -> int:
    return 1  # signals shutdown


def _cmd_analyze(ctx: ConsoleContext, args: list[str]) -> int:
    if not args:
        ctx.renderer.write_error("Usage: analyze <paper.pdf>")
        return 0
    path = Path(args[0]).expanduser().resolve()
    if not path.exists():
        ctx.renderer.write_error(f"Paper not found: {path}")
        return 0
    if path.suffix.lower() != ".pdf":
        ctx.renderer.write_error(f"Expected a PDF file: {path}")
        return 0
    workspace = ctx.session.workspace
    workspace.current_paper = path
    analysis = ctx.platform.analyze(path)
    workspace.current_analysis = analysis
    _workspace_store(ctx).save_analysis(analysis)
    ctx.renderer.render_command_success(
        message="Paper analyzed successfully",
        generated=("Analysis",),
        next_command="discover",
    )
    return 0


def _cmd_discover(ctx: ConsoleContext, _args: list[str]) -> int:
    workspace = ctx.session.workspace
    store = _workspace_store(ctx)
    hydrate_workspace_from_disk(workspace)

    analysis = workspace.current_analysis
    if analysis is None and workspace.current_paper is not None:
        analysis = ctx.platform.analyze(workspace.current_paper)
        workspace.current_analysis = analysis
        store.save_analysis(analysis)
    if analysis is None:
        diagnostic = diagnose_for_discover(store.root)
        if diagnostic is not None:
            ctx.renderer.write_error(render_diagnostic(diagnostic))
        else:
            ctx.renderer.write_error("No paper in session. Run: analyze <paper.pdf>")
        return 0

    discovery = ctx.platform.discover(analysis)
    workspace.current_discovery = discovery
    store.save_discovery(discovery)
    persist_discovery_decision_artifacts(store, discovery)
    ctx.renderer.render_command_success(
        message="Resources discovered",
        generated=("Discovery",),
        next_command="plan",
    )
    return 0


def _cmd_plan(ctx: ConsoleContext, _args: list[str]) -> int:
    workspace = ctx.session.workspace
    store = _workspace_store(ctx)
    hydrate_workspace_from_disk(workspace)

    analysis = workspace.current_analysis
    if analysis is None:
        diagnostic = diagnose_for_plan(store.root)
        if diagnostic is not None:
            ctx.renderer.write_error(render_diagnostic(diagnostic))
        else:
            ctx.renderer.write_error("No analysis in session. Run: analyze <paper.pdf>")
        return 0

    discovery = workspace.current_discovery
    if discovery is None:
        discovery = ctx.platform.discover(analysis)
        workspace.current_discovery = discovery
        store.save_discovery(discovery)

    strategy = ctx.platform.plan(analysis, discovery)
    workspace.current_strategy = strategy
    store.save_strategy(strategy)
    persist_planning_decision_artifacts(store, discovery, strategy)
    ctx.renderer.render_command_success(
        message="Execution strategy generated",
        generated=("Execution Strategy",),
        next_command="execute",
    )
    return 0


def _cmd_execute(ctx: ConsoleContext, args: list[str]) -> int:
    workspace = ctx.session.workspace

    resume = True
    run_id: str | None = None
    if args:
        if args[0] == "--no-resume":
            resume = False
            run_id = args[1] if len(args) > 1 else None
        else:
            run_id = args[0]

    try:
        outcome = ctx.platform.run_execution(run_id=run_id, resume=resume)
    except ValueError as exc:
        ctx.renderer.write_error(str(exc))
        return 0

    workspace.current_execution_run_id = outcome.run_id
    action = "resumed" if outcome.resumed else "started"
    ctx.renderer.write(f"✓ Execution run {action}: {outcome.run_id}")
    ctx.renderer.write(f"Status: {outcome.status.value}")
    ctx.renderer.write(f"Run directory: {outcome.run_directory}")
    if outcome.report is not None:
        ctx.renderer.write(f"Report: {outcome.run_directory}/report.json")
    ctx.renderer.write("")
    ctx.renderer.write("Next: execution status")
    return 0


def _cmd_execution(ctx: ConsoleContext, args: list[str]) -> int:
    if not args:
        ctx.renderer.write_error("Usage: execution <status|report> [run_id]")
        return 0

    subcommand = args[0]
    run_id = args[1] if len(args) > 1 else None

    if subcommand == "status":
        try:
            status = ctx.platform.execution_status(run_id)
        except ValueError as exc:
            ctx.renderer.write_error(str(exc))
            return 0
        ctx.renderer.write(f"Run: {status.run_id}")
        ctx.renderer.write(f"Status: {status.status.value}")
        ctx.renderer.write(f"Graph: {status.graph_id}")
        ctx.renderer.write(f"Backend: {status.backend_kind or 'n/a'}")
        ctx.renderer.write(f"Run directory: {status.run_directory}")
        if status.report_path is not None:
            ctx.renderer.write(f"Report: {status.report_path}")
        ctx.renderer.write("Tasks:")
        for task in status.tasks:
            ctx.renderer.write(f"  - {task.name} ({task.task_id}): {task.status.value}")
        return 0

    if subcommand == "report":
        try:
            report_view = ctx.platform.execution_report(run_id)
        except ValueError as exc:
            ctx.renderer.write_error(str(exc))
            return 0
        report = report_view.report
        ctx.renderer.write(f"Run: {report_view.run_id}")
        ctx.renderer.write(f"Status: {report.status.value}")
        ctx.renderer.write(f"Report path: {report_view.report_path}")
        ctx.renderer.write(f"Run directory: {report_view.run_directory}")
        if report_view.completed_task_ids:
            ctx.renderer.write("Completed tasks:")
            for task_id in report_view.completed_task_ids:
                ctx.renderer.write(f"  - {task_id}")
        if report_view.failed_task_ids:
            ctx.renderer.write("Failed tasks:")
            for task_id in report_view.failed_task_ids:
                ctx.renderer.write(f"  - {task_id}")
        if report_view.artifact_ids:
            ctx.renderer.write("Artifacts:")
            for artifact_id in report_view.artifact_ids:
                ctx.renderer.write(f"  - {artifact_id}")
        if report.summary:
            ctx.renderer.write("")
            ctx.renderer.write(report.summary)
        return 0

    ctx.renderer.write_error("Usage: execution <status|report> [run_id]")
    return 0


def _cmd_plan_all(ctx: ConsoleContext, args: list[str]) -> int:
    workspace = ctx.session.workspace
    store = _workspace_store(ctx)
    hydrate_workspace_from_disk(workspace)

    paper_path: Path | None = None
    if args:
        paper_path = Path(args[0]).expanduser().resolve()
        if not paper_path.exists():
            ctx.renderer.write_error(f"Paper not found: {paper_path}")
            return 0
        if paper_path.suffix.lower() != ".pdf":
            ctx.renderer.write_error(f"Expected a PDF file: {paper_path}")
            return 0
        workspace.current_paper = paper_path
    elif workspace.current_paper is not None:
        paper_path = workspace.current_paper
    else:
        diagnostic = diagnose_for_plan_all(store.root, has_paper=False)
        if diagnostic is not None:
            ctx.renderer.write_error(render_diagnostic(diagnostic))
        else:
            ctx.renderer.write_error("Usage: plan-all <paper.pdf>")
        return 0

    analysis = workspace.current_analysis
    if analysis is None:
        if paper_path is None:
            ctx.renderer.write_error("Usage: plan-all <paper.pdf>")
            return 0
        analysis = ctx.platform.analyze(paper_path)
        workspace.current_analysis = analysis
        store.save_analysis(analysis)

    discovery = workspace.current_discovery
    if discovery is None:
        discovery = ctx.platform.discover(analysis)
        workspace.current_discovery = discovery
        store.save_discovery(discovery)

    strategy = ctx.platform.plan(analysis, discovery)
    workspace.current_strategy = strategy
    store.save_strategy(strategy)
    persist_planning_decision_artifacts(store, discovery, strategy)
    ctx.renderer.render_command_success(
        message="Execution strategy generated",
        generated=("Analysis", "Discovery", "Execution Strategy"),
        next_command="execute",
    )
    return 0


def _cmd_execute_all(ctx: ConsoleContext, args: list[str]) -> int:
    return _cmd_execute(ctx, args)


def _cmd_reproduce(ctx: ConsoleContext, args: list[str]) -> int:
    code = _cmd_plan_all(ctx, args)
    if code != 0:
        return code
    return _cmd_execute(ctx, [])


def ensure_session_open(ctx: ConsoleContext) -> None:
    session = ctx.session
    workspace = session.workspace
    if workspace.workspace_root is None:
        workspace.workspace_root = ctx.platform.settings.workspace_root
    if session.state is SessionState.NEW:
        session.open()
    hydrate_workspace_from_disk(workspace)
