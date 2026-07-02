"""Man1Lab Python SDK — programmatic interface over the Platform Facade."""

from application.facade import DoctorReport, ExecuteResult
from application.version import PLATFORM_VERSION
from interfaces.sdk.client import Man1Lab

__all__ = [
    "PLATFORM_VERSION",
    "DoctorReport",
    "ExecuteResult",
    "Man1Lab",
]
