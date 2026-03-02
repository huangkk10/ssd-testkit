"""
OsConfig — PcaSvcAction

Disables the Program Compatibility Assistant service (PcaSvc), which
detects compatibility issues with older programs and can interfere with
automated test tool launches.

Mirrors Common.py ``disable_pcasvc_service()``.

Service: PcaSvc
Registry key: HKLM\\SYSTEM\\CurrentControlSet\\Services\\PcaSvc
"""

from ._base_service_action import BaseServiceAction


class PcaSvcAction(BaseServiceAction):
    """Disable Program Compatibility Assistant service (PcaSvc)."""

    name = "PcaSvcAction"
    service_name = "PcaSvc"
    capability_key = "pcasvc"
