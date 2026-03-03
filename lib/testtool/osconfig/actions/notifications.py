"""
OsConfig — NotificationAction

Disables Windows Notifications and Action Center via registry.

Registry path (per-machine, applies to all users)::

    HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer
        DisableNotificationCenter = 1  (disable Action Center / notifications)

For per-user suppression an additional HKCU key is used::

    HKCU\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer
        DisableNotificationCenter = 1
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
from ..registry_helper import write_value, delete_value, read_value_safe, REG_DWORD
from .base_action import AbstractOsAction

logger = get_module_logger(__name__)

_NOTIF_KEY_LM   = r"SOFTWARE\Policies\Microsoft\Windows\Explorer"
_NOTIF_KEY_CU   = r"SOFTWARE\Policies\Microsoft\Windows\Explorer"
_VAL_NOTIF      = "DisableNotificationCenter"
_SNAP_LM        = "notifications_hklm_orig"
_SNAP_CU        = "notifications_hkcu_orig"
_CAP_KEY        = "notifications"


class NotificationAction(AbstractOsAction):
    """
    Disable Windows Notifications / Action Center.

    Sets ``DisableNotificationCenter = 1`` in both HKLM and HKCU Explorer
    policy keys.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "NotificationAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when HKLM DisableNotificationCenter == 1."""
        v = read_value_safe("HKLM", _NOTIF_KEY_LM, _VAL_NOTIF, default=None)
        return v == 1

    def apply(self) -> None:
        """Set DisableNotificationCenter = 1 in HKLM and HKCU."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        for hive, key, snap_key in [
            ("HKLM", _NOTIF_KEY_LM, _SNAP_LM),
            ("HKCU", _NOTIF_KEY_CU, _SNAP_CU),
        ]:
            orig = read_value_safe(hive, key, _VAL_NOTIF, default=None)
            self._save_snapshot(snap_key, orig)
            write_value(hive, key, _VAL_NOTIF, 1, REG_DWORD)
            logger.debug(f"[{self.name}] {hive}\\...\\{_VAL_NOTIF}=1")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore DisableNotificationCenter to pre-apply state."""
        self._log_revert_start()

        for hive, key, snap_key in [
            ("HKLM", _NOTIF_KEY_LM, _SNAP_LM),
            ("HKCU", _NOTIF_KEY_CU, _SNAP_CU),
        ]:
            orig = self._load_snapshot(snap_key, default=None)
            if orig is not None:
                write_value(hive, key, _VAL_NOTIF, int(orig), REG_DWORD)
                logger.debug(f"[{self.name}] {hive} {_VAL_NOTIF} restored to {orig}")
            else:
                delete_value(hive, key, _VAL_NOTIF)
                logger.debug(f"[{self.name}] {hive} {_VAL_NOTIF} deleted (was absent)")

        self._log_revert_done()
