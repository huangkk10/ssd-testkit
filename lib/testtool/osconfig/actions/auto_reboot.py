"""
OsConfig — AutoRebootAction

Disables automatic reboot after a Blue Screen of Death (BSOD / kernel panic)
via the ``CrashControl`` registry key.

Registry path::

    HKLM\\SYSTEM\\CurrentControlSet\\Control\\CrashControl
        AutoReboot = 0  (disable auto reboot)
        AutoReboot = 1  (enable auto reboot – default)

Mirrors ``disable_auto_reboot()`` in Common.py.
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
from ..os_compat import WindowsBuildInfo, is_supported
from ..registry_helper import write_value, read_value_safe, REG_DWORD
from .base_action import AbstractOsAction

logger = get_module_logger(__name__)

_CC_KEY       = r"SYSTEM\CurrentControlSet\Control\CrashControl"
_VAL_REBOOT   = "AutoReboot"
_SNAP_REBOOT  = "auto_reboot_orig"
_CAP_KEY      = "auto_reboot"


class AutoRebootAction(AbstractOsAction):
    """
    Disable automatic reboot on BSOD (``AutoReboot = 0``).

    After a kernel crash the system will display the blue screen until
    manually rebooted, which allows capturing crash details.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "AutoRebootAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``AutoReboot == 0``."""
        v = read_value_safe("HKLM", _CC_KEY, _VAL_REBOOT, default=None)
        if v is None:
            return False
        return int(v) == 0

    def apply(self) -> None:
        """Set ``AutoReboot = 0``."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _CC_KEY, _VAL_REBOOT, default=None)
        self._save_snapshot(_SNAP_REBOOT, orig)
        logger.debug(f"[{self.name}] snapshot: {_VAL_REBOOT}={orig}")

        write_value("HKLM", _CC_KEY, _VAL_REBOOT, 0, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_REBOOT}=0 written")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore ``AutoReboot`` to its pre-apply value (default: 1)."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_REBOOT, default=None)
        restore = int(orig) if orig is not None else 1
        write_value("HKLM", _CC_KEY, _VAL_REBOOT, restore, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_REBOOT} restored to {restore}")

        self._log_revert_done()
