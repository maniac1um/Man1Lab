"""Startup profiling orchestration for the platform facade."""

from __future__ import annotations

import importlib
from dataclasses import replace

from configuration.models import TrackingConfig
from runtime.profiling import RuntimeProfiler, RuntimeProfile
from runtime.profiling.report import SessionProfileInfo


def profile_platform_startup() -> RuntimeProfile:
    """Profile platform import, configuration, facade, and workflow initialization."""
    profiler = RuntimeProfiler()

    with profiler.measure("Import"):
        importlib.import_module("configuration.bootstrap")
        importlib.import_module("application.facade")

    with profiler.measure("Configuration"):
        from configuration.bootstrap import initialize_app_configuration

        settings = initialize_app_configuration()

    profile_settings = replace(
        settings,
        tracking=TrackingConfig(enabled=False, backend="noop"),
    )

    with profiler.measure("Facade"):
        from application.facade import Man1Lab

        platform = Man1Lab(
            settings=profile_settings,
            initialize_configuration=False,
            configure_logging=False,
        )

    with profiler.measure("Workflow"):
        if not platform.is_runtime_ready():
            raise RuntimeError("Platform runtime is not ready.")
        _ = platform._orchestrator  # noqa: SLF001 — workflow wiring probe

    resource_statuses = platform.runtime.context.resource_status_entries()
    session = platform.runtime.session
    session_info = None
    if session.is_active():
        session_info = SessionProfileInfo(
            state=session.profile_state(),
            duration_s=session.duration_s(),
        )
    else:
        session_info = SessionProfileInfo(state=session.profile_state())

    return profiler.build_profile(
        resource_statuses=resource_statuses,
        session_info=session_info,
    )
