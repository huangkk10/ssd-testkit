"""
OsConfig — VulnDriverBlocklistAction

Disables the Vulnerable Driver Blocklist enforced by Windows CI (Code Integrity).

Registry path::

    HKLM\\SYSTEM\\CurrentControlSet\\Control\\CI\\Config
        VulnerableDriverBlocklistEnable

Setting ``VulnerableDriverBlocklistEnable = 0`` disables the kernel-mode
blocklist that prevents known vulnerable drivers from loading.

⚠️  **Security note**: Disabling the driver blocklist reduces kernel security.
This setting should only be used in controlled test environments where
specific device drivers would otherwise be blocked.

Mirrors ``disable_vulnerable_driver_blocklist()`` in Common.py.
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

_CI_KEY      = r"SYSTEM\CurrentControlSet\Control\CI\Config"
_VAL_BLOCKLIST = "VulnerableDriverBlocklistEnable"
_SNAP_ORIG   = "vuln_driver_blocklist_orig"
_CAP_KEY     = "vuln_driver_blocklist"


class VulnDriverBlocklistAction(AbstractOsAction):
    """
    Disable the Vulnerable Driver Blocklist (``VulnerableDriverBlocklistEnable = 0``).

    Primarily used before loading test or development drivers that are present
    on the Windows blocklist.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "VulnDriverBlocklistAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    # ------------------------------------------------------------------ #
    # AbstractOsAction interface                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        """Available on Windows 10/11 (all editions)."""
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """
        Return ``True`` when ``VulnerableDriverBlocklistEnable == 0``.

        An absent value means the default (enabled) is in effect → ``False``.
        """
        v = read_value_safe("HKLM", _CI_KEY, _VAL_BLOCKLIST, default=None)
        if v is None:
            return False   # absent = default enabled
        return int(v) == 0

    def apply(self) -> None:
        """Set ``VulnerableDriverBlocklistEnable = 0``."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _CI_KEY, _VAL_BLOCKLIST, default=None)
        self._save_snapshot(_SNAP_ORIG, orig)
        logger.debug(f"[{self.name}] snapshot: {_VAL_BLOCKLIST}={orig}")

        write_value("HKLM", _CI_KEY, _VAL_BLOCKLIST, 0, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_BLOCKLIST}=0 written")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore ``VulnerableDriverBlocklistEnable`` to its pre-apply value."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_ORIG, default=None)
        if orig is None:
            # Value was absent before – delete what we created
            delete_value("HKLM", _CI_KEY, _VAL_BLOCKLIST)
            logger.debug(f"[{self.name}] {_VAL_BLOCKLIST} deleted (was absent)")
        else:
            write_value("HKLM", _CI_KEY, _VAL_BLOCKLIST, int(orig), REG_DWORD)
            logger.debug(f"[{self.name}] {_VAL_BLOCKLIST} restored to {orig}")

        self._log_revert_done()
