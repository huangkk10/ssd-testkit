"""
OsConfig — AutoAdminLogonAction

Enables automatic administrator logon at Windows startup by setting the
``AutoAdminLogon`` registry value in the Winlogon key.

Registry path::

    HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon
        AutoAdminLogon = "1"   (enable auto logon)
        AutoAdminLogon = "0"   (disable auto logon – default)

⚠️  Setting ``AutoAdminLogon = "1"`` requires a default username to be
configured in ``DefaultUserName`` (and optionally ``DefaultPassword``,
``DefaultDomainName``).  This action only sets the ``AutoAdminLogon`` flag;
callers are responsible for ensuring the other Winlogon values are present.

Mirrors ``enable_auto_admin_logon()`` in Common.py.
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
from ..registry_helper import write_value, read_value_safe, REG_SZ
from .base_action import AbstractOsAction

logger = get_module_logger(__name__)

_WL_KEY      = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
_VAL_LOGON   = "AutoAdminLogon"
_SNAP_LOGON  = "auto_admin_logon_orig"
_CAP_KEY     = "auto_admin_logon"


class AutoAdminLogonAction(AbstractOsAction):
    """
    Enable automatic administrator logon (``AutoAdminLogon = "1"``).

    Sets the Winlogon registry value so the system logs in automatically
    at startup without showing the login prompt.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "AutoAdminLogonAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``AutoAdminLogon == "1"``."""
        v = read_value_safe("HKLM", _WL_KEY, _VAL_LOGON, default=None)
        if v is None:
            return False
        return str(v) == "1"

    def apply(self) -> None:
        """Set ``AutoAdminLogon = "1"``."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _WL_KEY, _VAL_LOGON, default=None)
        self._save_snapshot(_SNAP_LOGON, orig)
        logger.debug(f"[{self.name}] snapshot: {_VAL_LOGON}={orig!r}")

        write_value("HKLM", _WL_KEY, _VAL_LOGON, "1", REG_SZ)
        logger.debug(f"[{self.name}] {_VAL_LOGON}='1' written")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore ``AutoAdminLogon`` to its pre-apply value (default: "0")."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_LOGON, default=None)
        restore = str(orig) if orig is not None else "0"
        write_value("HKLM", _WL_KEY, _VAL_LOGON, restore, REG_SZ)
        logger.debug(f"[{self.name}] {_VAL_LOGON} restored to {restore!r}")

        self._log_revert_done()
