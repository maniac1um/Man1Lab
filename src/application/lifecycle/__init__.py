"""Platform lifecycle services — workspace initialization, validation, and cleanup."""

from application.lifecycle.clean import CleanPolicy, CleanupReport, clean_workspace
from application.lifecycle.common import format_check_status
from application.lifecycle.doctor import DoctorCheck, DoctorReport, run_doctor_checks
from application.lifecycle.init import InitAction, InitReport, init_workspace

__all__ = [
    "CleanPolicy",
    "CleanupReport",
    "DoctorCheck",
    "DoctorReport",
    "InitAction",
    "InitReport",
    "clean_workspace",
    "format_check_status",
    "init_workspace",
    "run_doctor_checks",
]
