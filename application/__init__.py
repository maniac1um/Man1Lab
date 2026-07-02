"""Man1Lab platform application layer — public entry point."""

from application.facade import DoctorReport, ExecuteResult, Man1Lab
from application.lifecycle import InitReport
from application.version import PLATFORM_VERSION

__all__ = [
    "PLATFORM_VERSION",
    "DoctorReport",
    "ExecuteResult",
    "InitReport",
    "Man1Lab",
]
