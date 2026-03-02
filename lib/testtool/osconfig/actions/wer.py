"""
OsConfig — WerAction

Disables the Windows Error Reporting service (WerSvc), which collects
and uploads crash data. On test machines this avoids pop-up dialogs and
background upload activity after a driver crash.

Service: WerSvc
Registry key: HKLM\\SYSTEM\\CurrentControlSet\\Services\\WerSvc
"""

from ._base_service_action import BaseServiceAction


class WerAction(BaseServiceAction):
    """Disable Windows Error Reporting service (WerSvc)."""

    name = "WerAction"
    service_name = "WerSvc"
    capability_key = "wer"
