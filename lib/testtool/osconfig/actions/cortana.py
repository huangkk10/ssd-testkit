"""
OsConfig — CortanaAction

Disables Cortana via the Windows Search Group Policy registry key.

Registry path::

    HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Windows Search
        AllowCortana = 0  (disable Cortana)
        AllowCortana = 1  (enable Cortana)

On Windows 11 21H2+, Cortana is a separate optional app and this key may
not have any effect; the action applies the registry value regardless.
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

_CORTANA_KEY  = r"SOFTWARE\Policies\Microsoft\Windows\Windows Search"
_VAL_CORTANA  = "AllowCortana"
_SNAP_CORTANA = "cortana_orig"
_CAP_KEY      = "cortana"


class CortanaAction(AbstractOsAction):
    """
    Disable Cortana (``AllowCortana = 0``).

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "CortanaAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``AllowCortana == 0``."""
        v = read_value_safe("HKLM", _CORTANA_KEY, _VAL_CORTANA, default=None)
        if v is None:
            return False
        return int(v) == 0

    def apply(self) -> None:
        """Set ``AllowCortana = 0``."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _CORTANA_KEY, _VAL_CORTANA, default=None)
        self._save_snapshot(_SNAP_CORTANA, orig)

        write_value("HKLM", _CORTANA_KEY, _VAL_CORTANA, 0, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_CORTANA}=0 written")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore ``AllowCortana`` to its pre-apply value."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_CORTANA, default=None)
        if orig is not None:
            write_value("HKLM", _CORTANA_KEY, _VAL_CORTANA, int(orig), REG_DWORD)
            logger.debug(f"[{self.name}] {_VAL_CORTANA} restored to {orig}")
        else:
            delete_value("HKLM", _CORTANA_KEY, _VAL_CORTANA)
            logger.debug(f"[{self.name}] {_VAL_CORTANA} deleted (was absent)")

        self._log_revert_done()
