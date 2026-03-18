"""
OsConfig  AutoAdminLogonAction

Enables automatic administrator logon at Windows startup by setting the
``AutoAdminLogon`` registry value (and companion credential values) in the
Winlogon key.

Registry path::

    HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon
        AutoAdminLogon   = "1"           (enable) / "0" (disable)
        DefaultUserName  = "<username>"  (required for auto-logon to work)
        DefaultPassword  = "<password>"  ( stored as plaintext  use on lab
                                           machines only)
        DefaultDomainName = "<domain>"   (optional; "." or "" for local account)

  **Security notice**: ``DefaultPassword`` is stored in plaintext under
HKLM.  Only use this on isolated lab / test machines.  Never enable on
production or shared systems.

Mirrors ``enable_auto_admin_logon()`` in Common.py with the addition of full
credential management via ``username`` / ``password`` / ``domain`` parameters.
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
from ..registry_helper import write_value, read_value_safe, delete_value, REG_SZ
from .base_action import AbstractOsAction

logger = get_module_logger(__name__)

_WL_KEY           = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
_VAL_LOGON        = "AutoAdminLogon"
_VAL_USERNAME     = "DefaultUserName"
_VAL_PASSWORD     = "DefaultPassword"
_VAL_DOMAIN       = "DefaultDomainName"

_SNAP_LOGON       = "auto_admin_logon_orig"
_SNAP_USERNAME    = "auto_admin_logon_username_orig"
_SNAP_PASSWORD    = "auto_admin_logon_password_orig"
_SNAP_DOMAIN      = "auto_admin_logon_domain_orig"

_CAP_KEY          = "auto_admin_logon"

# Sentinel used to distinguish "key did not exist" from "key was empty string"
_MISSING = object()


class AutoAdminLogonAction(AbstractOsAction):
    """
    Enable automatic administrator logon (``AutoAdminLogon = "1"``).

    Sets the Winlogon registry values so the system logs in automatically at
    startup without showing the login prompt.

    When *username* is supplied the action also writes ``DefaultUserName``,
    ``DefaultPassword`` (if *password* is provided), and ``DefaultDomainName``
    (if *domain* is provided).  On ``revert()`` all touched values are
    restored to their original state; values that did not previously exist are
    deleted rather than set to an empty string.

    Args:
        username:       Windows account name to log in automatically (e.g.
                        ``"Administrator"``).  If ``None`` the action only
                        sets the ``AutoAdminLogon`` flag and leaves the
                        credential values untouched.
        password:       Password for *username*.  Stored in plaintext in the
                        registry  only suitable for isolated lab machines.
        domain:         NetBIOS domain name.  Use ``"."`` or ``""`` for a local
                        account.  Defaults to ``None`` (leave unchanged).
        snapshot_store: Optional shared snapshot dict.
    """

    name = "AutoAdminLogonAction"

    def __init__(
        self,
        username:       Optional[str] = None,
        password:       Optional[str] = None,
        domain:         Optional[str] = None,
        snapshot_store: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(snapshot_store)
        self._username = username
        self._password = password
        self._domain   = domain

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """
        Return ``True`` when the system is already in the target state.

        Checks ``AutoAdminLogon == "1"`` and, when a *username* was given,
        that ``DefaultUserName`` matches.
        """
        logon = read_value_safe("HKLM", _WL_KEY, _VAL_LOGON, default=None)
        if str(logon) != "1":
            return False
        if self._username is not None:
            current_user = read_value_safe("HKLM", _WL_KEY, _VAL_USERNAME, default=None)
            if current_user != self._username:
                return False
        return True

    def apply(self) -> None:
        """Set ``AutoAdminLogon = "1"`` and write credential values."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        #  snapshot originals 
        orig_logon = read_value_safe("HKLM", _WL_KEY, _VAL_LOGON, default=_MISSING)
        self._save_snapshot(_SNAP_LOGON, orig_logon)
        logger.debug(f"[{self.name}] snapshot: {_VAL_LOGON}={orig_logon!r}")

        if self._username is not None:
            orig_user = read_value_safe("HKLM", _WL_KEY, _VAL_USERNAME, default=_MISSING)
            self._save_snapshot(_SNAP_USERNAME, orig_user)
            logger.debug(f"[{self.name}] snapshot: {_VAL_USERNAME}={orig_user!r}")

        if self._password is not None:
            orig_pass = read_value_safe("HKLM", _WL_KEY, _VAL_PASSWORD, default=_MISSING)
            self._save_snapshot(_SNAP_PASSWORD, orig_pass)
            logger.debug(f"[{self.name}] snapshot: {_VAL_PASSWORD}=<redacted>")

        if self._domain is not None:
            orig_dom = read_value_safe("HKLM", _WL_KEY, _VAL_DOMAIN, default=_MISSING)
            self._save_snapshot(_SNAP_DOMAIN, orig_dom)
            logger.debug(f"[{self.name}] snapshot: {_VAL_DOMAIN}={orig_dom!r}")

        #  apply 
        write_value("HKLM", _WL_KEY, _VAL_LOGON, "1", REG_SZ)
        logger.debug(f"[{self.name}] {_VAL_LOGON}='1' written")

        if self._username is not None:
            write_value("HKLM", _WL_KEY, _VAL_USERNAME, self._username, REG_SZ)
            logger.debug(f"[{self.name}] {_VAL_USERNAME}={self._username!r} written")

        if self._password is not None:
            write_value("HKLM", _WL_KEY, _VAL_PASSWORD, self._password, REG_SZ)
            logger.debug(f"[{self.name}] {_VAL_PASSWORD}=<redacted> written")

        if self._domain is not None:
            write_value("HKLM", _WL_KEY, _VAL_DOMAIN, self._domain, REG_SZ)
            logger.debug(f"[{self.name}] {_VAL_DOMAIN}={self._domain!r} written")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore all touched Winlogon values to their pre-apply state."""
        self._log_revert_start()

        #  AutoAdminLogon 
        orig_logon = self._load_snapshot(_SNAP_LOGON, default=_MISSING)
        if orig_logon is _MISSING:
            # Value did not exist before  remove it
            delete_value("HKLM", _WL_KEY, _VAL_LOGON)
            logger.debug(f"[{self.name}] {_VAL_LOGON} deleted (was absent before apply)")
        else:
            restore = str(orig_logon) if orig_logon is not None else "0"
            write_value("HKLM", _WL_KEY, _VAL_LOGON, restore, REG_SZ)
            logger.debug(f"[{self.name}] {_VAL_LOGON} restored to {restore!r}")

        #  DefaultUserName 
        if self._username is not None:
            orig_user = self._load_snapshot(_SNAP_USERNAME, default=_MISSING)
            if orig_user is _MISSING:
                delete_value("HKLM", _WL_KEY, _VAL_USERNAME)
                logger.debug(f"[{self.name}] {_VAL_USERNAME} deleted")
            else:
                write_value("HKLM", _WL_KEY, _VAL_USERNAME, str(orig_user), REG_SZ)
                logger.debug(f"[{self.name}] {_VAL_USERNAME} restored to {orig_user!r}")

        #  DefaultPassword 
        if self._password is not None:
            orig_pass = self._load_snapshot(_SNAP_PASSWORD, default=_MISSING)
            if orig_pass is _MISSING:
                delete_value("HKLM", _WL_KEY, _VAL_PASSWORD)
                logger.debug(f"[{self.name}] {_VAL_PASSWORD} deleted")
            else:
                write_value("HKLM", _WL_KEY, _VAL_PASSWORD, str(orig_pass), REG_SZ)
                logger.debug(f"[{self.name}] {_VAL_PASSWORD} restored")

        #  DefaultDomainName 
        if self._domain is not None:
            orig_dom = self._load_snapshot(_SNAP_DOMAIN, default=_MISSING)
            if orig_dom is _MISSING:
                delete_value("HKLM", _WL_KEY, _VAL_DOMAIN)
                logger.debug(f"[{self.name}] {_VAL_DOMAIN} deleted")
            else:
                write_value("HKLM", _WL_KEY, _VAL_DOMAIN, str(orig_dom), REG_SZ)
                logger.debug(f"[{self.name}] {_VAL_DOMAIN} restored to {orig_dom!r}")

        self._log_revert_done()
