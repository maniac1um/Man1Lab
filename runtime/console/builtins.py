"""Built-in Man1Lab console commands."""

from __future__ import annotations

from pathlib import Path

from runtime.console.command import ConsoleCommand, ConsoleContext
from runtime.console.registry import CommandRegistry
from runtime.session.state import SessionState


def _format_check_status(status: str) -> str:
    return {"ok": "✓", "warn": "⚠", "fail": "✗"}.get(status, status)


def register_builtin_commands(registry: CommandRegistry) -> None:
    """Register the initial interactive console command set."""
    commands = (
        ConsoleCommand("help", "Show available commands.", _cmd_help),
        ConsoleCommand("doctor", "Validate runtime environment.", _cmd_doctor),
        ConsoleCommand("profile", "Profile startup and runtime initialization.", _cmd_profile),
        ConsoleCommand("model", "Model profile commands (list, current, use).", _cmd_model),
        ConsoleCommand("clear", "Clear the console screen.", _cmd_clear),
        ConsoleCommand("exit", "Exit the console.", _cmd_exit),
        ConsoleCommand("analyze", "Analyze a paper PDF.", _cmd_analyze),
        ConsoleCommand("discover", "Run discovery for the current paper.", _cmd_discover),
        ConsoleCommand("plan", "Run execution planning for the current session.", _cmd_plan),
    )
    for command in commands:
        registry.register(command)


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
    ctx.renderer.write(f"Analysis complete: {analysis.metadata.title}")
    return 0


def _cmd_discover(ctx: ConsoleContext, _args: list[str]) -> int:
    workspace = ctx.session.workspace
    analysis = workspace.current_analysis
    if analysis is None and workspace.current_paper is not None:
        analysis = ctx.platform.analyze(workspace.current_paper)
        workspace.current_analysis = analysis
    if analysis is None:
        ctx.renderer.write_error("No paper in session. Run: analyze <paper.pdf>")
        return 0
    discovery = ctx.platform.discover(analysis)
    workspace.current_discovery = discovery
    ctx.renderer.write(f"Discovery complete: {discovery.metadata.status.value}")
    return 0


def _cmd_plan(ctx: ConsoleContext, _args: list[str]) -> int:
    workspace = ctx.session.workspace
    analysis = workspace.current_analysis
    if analysis is None:
        ctx.renderer.write_error("No analysis in session. Run: analyze <paper.pdf>")
        return 0
    discovery = workspace.current_discovery
    if discovery is None:
        discovery = ctx.platform.discover(analysis)
        workspace.current_discovery = discovery
    strategy = ctx.platform.plan(analysis, discovery)
    workspace.current_strategy = strategy
    ctx.renderer.write(f"Planning complete: {strategy.strategy_id}")
    return 0


def ensure_session_open(ctx: ConsoleContext) -> None:
    session = ctx.session
    if session.state is SessionState.NEW:
        session.open()
