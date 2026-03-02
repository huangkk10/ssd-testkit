"""
OsConfig — SysMainAction

Disables the SysMain service (formerly known as SuperFetch), which
pre-loads frequently used applications into memory. On test machines
the behaviour can cause unpredictable disk and memory activity.

Service: SysMain
Registry key: HKLM\\SYSTEM\\CurrentControlSet\\Services\\SysMain
"""

from ._base_service_action import BaseServiceAction


class SysMainAction(BaseServiceAction):
    """Disable SysMain / Superfetch service."""

    name = "SysMainAction"
    service_name = "SysMain"
    capability_key = "sysmain"
