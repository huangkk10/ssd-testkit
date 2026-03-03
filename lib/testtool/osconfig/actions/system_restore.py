"""
OsConfig — SystemRestoreAction

Disables Windows System Restore (Volume Shadow Copy protection points)
on the system drive by calling ``Disable-ComputerRestore`` via PowerShell,
or directly via the ``SystemRestorePointCreationFrequency`` registry value.

Registry path::

    HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore
        DisableSR = 1  (disable, XP compatibility key)

PowerShell::

    apply()  → Disable-ComputerRestore -Drive "C:\\"
    revert() → Enable-ComputerRestore  -Drive "C:\\"

⚠️  Not available on Server editions (no Volume Shadow service context).
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
from ..exceptions import OsConfigActionError
from .base_action import AbstractOsAction
from ._helpers import run_powershell

logger = get_module_logger(__name__)

_SR_KEY     = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore"
_VAL_SR     = "DisableSR"
_SNAP_SR    = "system_restore_sr_orig"
_CAP_KEY    = "system_restore"
_DRIVE      = "C:\\"


class SystemRestoreAction(AbstractOsAction):
    """
    Disable Windows System Restore on the C:\\ drive.

    Uses ``Disable-ComputerRestore`` PowerShell CmdLet and also sets
    the ``DisableSR`` registry value as a belt-and-suspenders approach.

    ⚠️  Not supported on Server editions.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "SystemRestoreAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        """System Restore is not available on Server editions."""
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``DisableSR == 1``."""
        v = read_value_safe("HKLM", _SR_KEY, _VAL_SR, default=None)
        return v == 1

    def apply(self) -> None:
        """Disable System Restore via PowerShell and registry."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _SR_KEY, _VAL_SR, default=None)
        self._save_snapshot(_SNAP_SR, orig)

        # PowerShell (best effort)
        ps_rc = run_powershell(f'Disable-ComputerRestore -Drive "{_DRIVE}"')
        if ps_rc != 0:
            logger.warning(f"[{self.name}] Disable-ComputerRestore returned rc={ps_rc}")

        # Registry fallback
        write_value("HKLM", _SR_KEY, _VAL_SR, 1, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_SR}=1 written")

        self._log_apply_done()

    def revert(self) -> None:
        """Re-enable System Restore."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_SR, default=None)

        ps_rc = run_powershell(f'Enable-ComputerRestore -Drive "{_DRIVE}"')
        if ps_rc != 0:
            logger.warning(f"[{self.name}] Enable-ComputerRestore returned rc={ps_rc}")

        restore = int(orig) if orig is not None else 0
        write_value("HKLM", _SR_KEY, _VAL_SR, restore, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_SR} restored to {restore}")

        self._log_revert_done()
