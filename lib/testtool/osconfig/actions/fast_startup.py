"""
OsConfig — FastStartupAction

Disables Windows Fast Startup (Hybrid Boot / Hiberboot) by setting the
``HiberbootEnabled`` registry value to 0.

Fast Startup uses a partial hibernation (saves kernel state) instead of a
full shutdown, which can cause issues with storage test equipment that needs
a clean power cycle.

Registry path::

    HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Power
        HiberbootEnabled = 0  (disable Fast Startup)
        HiberbootEnabled = 1  (enable Fast Startup – default)
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

_FS_KEY   = r"SYSTEM\CurrentControlSet\Control\Session Manager\Power"
_VAL_FS   = "HiberbootEnabled"
_SNAP_FS  = "fast_startup_orig"
_CAP_KEY  = "fast_startup"


class FastStartupAction(AbstractOsAction):
    """
    Disable Fast Startup (``HiberbootEnabled = 0``).

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "FastStartupAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``HiberbootEnabled == 0``."""
        v = read_value_safe("HKLM", _FS_KEY, _VAL_FS, default=None)
        if v is None:
            return False
        return int(v) == 0

    def apply(self) -> None:
        """Set ``HiberbootEnabled = 0``."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _FS_KEY, _VAL_FS, default=None)
        self._save_snapshot(_SNAP_FS, orig)
        logger.debug(f"[{self.name}] snapshot: {_VAL_FS}={orig}")

        write_value("HKLM", _FS_KEY, _VAL_FS, 0, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_FS}=0 written")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore ``HiberbootEnabled`` to its pre-apply value (default: 1)."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_FS, default=None)
        restore = int(orig) if orig is not None else 1
        write_value("HKLM", _FS_KEY, _VAL_FS, restore, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_FS} restored to {restore}")

        self._log_revert_done()
