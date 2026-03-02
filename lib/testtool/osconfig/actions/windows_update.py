"""
OsConfig — WindowsUpdateAction

Disables the Windows Update service (wuauserv) to prevent automatic
updates from interrupting long-running storage tests.

Mirrors the behaviour of Common.py ``disable_windows_auto_update()``,
but uses the structured Action interface with snapshot / revert support.

Service: wuauserv
Registry key: HKLM\\SYSTEM\\CurrentControlSet\\Services\\wuauserv
Additional GPO registry setting applied in ``apply()``::

    HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU
        NoAutoUpdate = 1  (REG_DWORD)
"""

from __future__ import annotations

import sys
import os
from typing import Optional, Dict, Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.logger import get_module_logger
from ..registry_helper import (
    write_value, delete_value, read_value_safe, REG_DWORD
)
from ..os_compat import WindowsBuildInfo
from ._base_service_action import BaseServiceAction

logger = get_module_logger(__name__)

_GPO_KEY  = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
_GPO_VAL  = "NoAutoUpdate"
_SNAP_GPO = "no_auto_update_gpo"


class WindowsUpdateAction(BaseServiceAction):
    """
    Disable Windows Update service (wuauserv) and set NoAutoUpdate GPO.

    Extends :class:`BaseServiceAction` to also write / remove the
    ``NoAutoUpdate`` Group Policy registry value.
    """

    name = "WindowsUpdateAction"
    service_name = "wuauserv"
    capability_key = "windows_update"

    def apply(self) -> None:
        # Snapshot GPO value before parent apply()
        gpo_orig = read_value_safe("HKLM", _GPO_KEY, _GPO_VAL, default=None)
        self._save_snapshot(_SNAP_GPO, gpo_orig)

        # Set GPO key (creates the key hierarchy if needed)
        write_value("HKLM", _GPO_KEY, _GPO_VAL, 1, REG_DWORD)
        logger.debug(f"[{self.name}] NoAutoUpdate GPO set to 1")

        # Let the parent handle service stop + disable
        super().apply()

    def revert(self) -> None:
        # Restore parent service state first
        super().revert()

        # Restore GPO value
        gpo_orig = self._load_snapshot(_SNAP_GPO, default=None)
        if gpo_orig is not None:
            write_value("HKLM", _GPO_KEY, _GPO_VAL, int(gpo_orig), REG_DWORD)
            logger.debug(f"[{self.name}] NoAutoUpdate GPO restored to {gpo_orig}")
        else:
            # Was not set before – remove it
            delete_value("HKLM", _GPO_KEY, _GPO_VAL)
            logger.debug(f"[{self.name}] NoAutoUpdate GPO deleted (was absent)")
