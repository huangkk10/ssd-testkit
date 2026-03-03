"""
OsConfig — UacAction

Disables User Account Control (UAC) by setting ``EnableLUA = 0`` in the
Windows Policies system registry key.

Registry path::

    HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System
        EnableLUA = 0   (disable UAC)
        EnableLUA = 1   (enable UAC – default)

The change takes effect after reboot.

Mirrors ``disable_user_notification()`` in Common.py.
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

_UAC_KEY   = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
_VAL_LUA   = "EnableLUA"
_SNAP_LUA  = "uac_enable_lua_orig"
_CAP_KEY   = "uac"


class UacAction(AbstractOsAction):
    """
    Disable User Account Control (``EnableLUA = 0``).

    Sets the ``EnableLUA`` policy to 0 so that administrative processes run
    without UAC elevation prompts.  Requires a reboot to take full effect.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "UacAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    # ------------------------------------------------------------------ #
    # AbstractOsAction interface                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        """UAC control is available on all supported Windows builds."""
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``EnableLUA == 0`` (UAC disabled)."""
        v = read_value_safe("HKLM", _UAC_KEY, _VAL_LUA, default=None)
        if v is None:
            # UAC key always exists on modern Windows; None is unexpected.
            # Treat as enabled (not yet disabled).
            return False
        return int(v) == 0

    def apply(self) -> None:
        """Set ``EnableLUA = 0`` to disable UAC."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _UAC_KEY, _VAL_LUA, default=None)
        self._save_snapshot(_SNAP_LUA, orig)
        logger.debug(f"[{self.name}] snapshot: {_VAL_LUA}={orig}")

        write_value("HKLM", _UAC_KEY, _VAL_LUA, 0, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_LUA}=0 written (reboot required)")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore ``EnableLUA`` to its pre-apply value (default: 1)."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_LUA, default=None)
        restore_val = int(orig) if orig is not None else 1   # safe default: re-enable UAC
        write_value("HKLM", _UAC_KEY, _VAL_LUA, restore_val, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_LUA} restored to {restore_val}")

        self._log_revert_done()
