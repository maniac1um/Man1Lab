"""LLM configuration checks for doctor reports."""

from __future__ import annotations

from application.lifecycle.doctor import DoctorCheck
from providers.llm.manager import LLMManager


def run_llm_doctor_checks(llm_manager: LLMManager) -> list[DoctorCheck]:
    registry = llm_manager.model_registry
    profiles = registry.list_profiles()
    validation = registry.validate()
    current = registry.get_active_profile()

    checks: list[DoctorCheck] = [
        DoctorCheck(
            name="LLM Profiles",
            status="ok" if profiles else "warn",
            message=str(len(profiles)),
        )
    ]

    if current is None:
        checks.append(
            DoctorCheck(
                name="LLM Active",
                status="warn",
                message="No active profile configured.",
            )
        )
        checks.append(
            DoctorCheck(
                name="LLM Validation",
                status="fail" if not validation.valid else "warn",
                message=_validation_summary(validation),
            )
        )
        return checks

    checks.extend(
        [
            DoctorCheck(name="LLM Active", status="ok", message=current.profile_name),
            DoctorCheck(
                name="LLM Provider",
                status="ok",
                message=current.provider.capitalize(),
            ),
            DoctorCheck(name="LLM Model", status="ok", message=current.model),
        ]
    )

    api_key = registry.resolve_api_key(current)
    if api_key:
        checks.append(
            DoctorCheck(name="LLM API Key", status="ok", message="Configured")
        )
    else:
        checks.append(
            DoctorCheck(
                name="LLM API Key",
                status="fail",
                message=f"Missing reference: {current.api_key_reference}",
            )
        )

    if api_key and llm_manager.has_active_provider():
        test_report = llm_manager.test_model(current.profile_name)
        if test_report.result == "passed":
            latency = (
                f" ({test_report.latency_ms} ms)"
                if test_report.latency_ms is not None
                else ""
            )
            checks.append(
                DoctorCheck(
                    name="LLM Connection",
                    status="ok",
                    message=f"Healthy{latency}",
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    name="LLM Connection",
                    status="warn",
                    message=test_report.message,
                )
            )
    elif api_key:
        checks.append(
            DoctorCheck(
                name="LLM Connection",
                status="warn",
                message="Provider unavailable for health check.",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="LLM Connection",
                status="warn",
                message="Skipped — API key not configured.",
            )
        )

    validation_status = "ok" if validation.valid else "fail"
    checks.append(
        DoctorCheck(
            name="LLM Validation",
            status=validation_status,
            message=_validation_summary(validation),
        )
    )
    return checks


def _validation_summary(validation) -> str:
    if validation.valid:
        return "Passed"
    if validation.errors:
        return validation.errors[0].message
    return "Validation failed"
