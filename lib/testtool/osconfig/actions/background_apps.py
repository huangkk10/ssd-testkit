"""
OsConfig — BackgroundAppsAction

Disables Windows background app processing via the Global User Service
policy registry key.

Registry path::

    HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\AppPrivacy
        LetAppsRunInBackground = 2  (force deny all background apps)
        LetAppsRunInBackground = 0  (user controlled – default)

Value semantics:
    0 = User in control
    1 = Force allow
    2 = Force deny
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

_BG_KEY   = r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy"
_VAL_BG   = "LetAppsRunInBackground"
_SNAP_BG  = "background_apps_orig"
_CAP_KEY  = "background_apps"

_FORCE_DENY = 2


class BackgroundAppsAction(AbstractOsAction):
    """
    Disable background app processing (``LetAppsRunInBackground = 2``).

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "BackgroundAppsAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``LetAppsRunInBackground == 2``."""
        v = read_value_safe("HKLM", _BG_KEY, _VAL_BG, default=None)
        if v is None:
            return False
        return int(v) == _FORCE_DENY

    def apply(self) -> None:
        """Set ``LetAppsRunInBackground = 2``."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _BG_KEY, _VAL_BG, default=None)
        self._save_snapshot(_SNAP_BG, orig)

        write_value("HKLM", _BG_KEY, _VAL_BG, _FORCE_DENY, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_BG}={_FORCE_DENY} written")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore ``LetAppsRunInBackground`` to its pre-apply value."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_BG, default=None)
        if orig is not None:
            write_value("HKLM", _BG_KEY, _VAL_BG, int(orig), REG_DWORD)
            logger.debug(f"[{self.name}] {_VAL_BG} restored to {orig}")
        else:
            delete_value("HKLM", _BG_KEY, _VAL_BG)
            logger.debug(f"[{self.name}] {_VAL_BG} deleted (was absent)")

        self._log_revert_done()
