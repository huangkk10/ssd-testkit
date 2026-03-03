"""
OsConfig — OneDriveAction

Disables OneDrive metered-network sync and file-storage via Group Policy
registry keys under::

    HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\OneDrive

Requires Windows RS1 (Build ≥ 14393).  On earlier builds ``supported_on()``
returns ``False`` and ``apply()`` skips without raising.

Registry values managed
-----------------------
* ``DisableMeteredNetworkFileSync``    – stop OneDrive syncing on metered networks
* ``DisableFileSyncNGSC``              – prevent users from syncing files to OneDrive
* ``PreventNetworkTrafficPreUserSignIn`` – block network traffic before sign-in

All three values are snapshotted before the first write and restored on
``revert()``.
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
from ..exceptions import OsConfigNotSupportedError, OsConfigActionError
from .base_action import AbstractOsAction

logger = get_module_logger(__name__)

_OD_KEY        = r"SOFTWARE\Policies\Microsoft\Windows\OneDrive"
_VAL_METERED   = "DisableMeteredNetworkFileSync"
_VAL_FILESYNC  = "DisableFileSyncNGSC"
_VAL_PRELOGON  = "PreventNetworkTrafficPreUserSignIn"

# Snapshot keys
_SNAP_METERED  = "od_metered_orig"
_SNAP_FILESYNC = "od_filesync_orig"
_SNAP_PRELOGON = "od_prelogon_orig"

_CAP_KEY = "onedrive_metered"   # requires Build ≥ 14393 (RS1)


class OneDriveAction(AbstractOsAction):
    """
    Disable OneDrive via Group Policy registry keys.

    Applies three registry values that together prevent OneDrive from
    syncing data or communicating on the network.  Requires Windows RS1
    (Build ≥ 14393); silently skips on older builds unless *fail_on_unsupported*
    is ``True``.

    Args:
        snapshot_store:       Optional shared snapshot dict.
        fail_on_unsupported:  If ``True``, raise
            :class:`~lib.testtool.osconfig.exceptions.OsConfigNotSupportedError`
            when the OS build does not support this action.  Default: ``False``.
    """

    name = "OneDriveAction"

    def __init__(
        self,
        snapshot_store: Optional[Dict[str, Any]] = None,
        fail_on_unsupported: bool = False,
    ) -> None:
        super().__init__(snapshot_store)
        self._fail_on_unsupported = fail_on_unsupported

    # ------------------------------------------------------------------ #
    # AbstractOsAction interface                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        """Return ``True`` for Windows RS1 (Build ≥ 14393) and later."""
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """
        Return ``True`` when all three OneDrive GPO values are set to 1.
        Returns ``False`` if any value is absent or not equal to 1.
        """
        for val_name in (_VAL_METERED, _VAL_FILESYNC, _VAL_PRELOGON):
            v = read_value_safe("HKLM", _OD_KEY, val_name, default=None)
            if v != 1:
                return False
        return True

    def apply(self) -> None:
        """Set all three OneDrive GPO registry values to 1."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        # Snapshot current values (may be None if key/value absent)
        for snap_key, val_name in [
            (_SNAP_METERED,  _VAL_METERED),
            (_SNAP_FILESYNC, _VAL_FILESYNC),
            (_SNAP_PRELOGON, _VAL_PRELOGON),
        ]:
            orig = read_value_safe("HKLM", _OD_KEY, val_name, default=None)
            self._save_snapshot(snap_key, orig)

        logger.debug(f"[{self.name}] snapshots saved")

        # Write target values
        for val_name in (_VAL_METERED, _VAL_FILESYNC, _VAL_PRELOGON):
            write_value("HKLM", _OD_KEY, val_name, 1, REG_DWORD)
            logger.debug(f"[{self.name}] set {val_name}=1")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore OneDrive GPO registry values to their pre-apply state."""
        self._log_revert_start()

        for snap_key, val_name in [
            (_SNAP_METERED,  _VAL_METERED),
            (_SNAP_FILESYNC, _VAL_FILESYNC),
            (_SNAP_PRELOGON, _VAL_PRELOGON),
        ]:
            orig = self._load_snapshot(snap_key, default=None)
            if orig is not None:
                write_value("HKLM", _OD_KEY, val_name, int(orig), REG_DWORD)
                logger.debug(f"[{self.name}] restored {val_name}={orig}")
            else:
                delete_value("HKLM", _OD_KEY, val_name)
                logger.debug(f"[{self.name}] deleted {val_name} (was absent)")

        self._log_revert_done()
