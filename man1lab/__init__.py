"""Man1Lab public Python package."""

from interfaces.sdk import PLATFORM_VERSION, DoctorReport, ExecuteResult, Man1Lab

__all__ = [
    "PLATFORM_VERSION",
    "DoctorReport",
    "ExecuteResult",
    "Man1Lab",
]

__version__ = PLATFORM_VERSION
