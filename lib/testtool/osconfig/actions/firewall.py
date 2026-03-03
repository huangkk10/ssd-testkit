"""
OsConfig — FirewallAction

Disables the Windows Firewall on all profiles (Domain, Private, Public) via
``netsh advfirewall``.

Commands used::

    apply()  → netsh advfirewall set allprofiles state off
    revert() → netsh advfirewall set allprofiles state on
    check()  → netsh advfirewall show allprofiles  (parse "State" lines)

The current per-profile state is not individually snapshotted – on revert all
profiles are restored to ``on``.  In most test environments this is the correct
pre-apply state; a more granular implementation could parse each profile's
state before ``apply()`` if needed.

Mirrors ``disable_firewall()`` in Common.py.
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
from ..exceptions import OsConfigActionError
from .base_action import AbstractOsAction
from ._helpers import run_command, run_command_with_output

logger = get_module_logger(__name__)

_CAP_KEY = "firewall"


class FirewallAction(AbstractOsAction):
    """
    Disable Windows Firewall on all profiles.

    Uses ``netsh advfirewall`` to turn the firewall off / on.
    ``check()`` parses ``netsh advfirewall show allprofiles`` to determine
    whether all profiles report ``State                                ON``.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "FirewallAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    # ------------------------------------------------------------------ #
    # AbstractOsAction interface                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        """Firewall management is available on all supported builds."""
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """
        Return ``True`` when all firewall profiles report ``State OFF``.

        Parses the output of ``netsh advfirewall show allprofiles``.
        If the command fails or the output cannot be parsed, returns ``False``.
        """
        rc, stdout, _ = run_command_with_output("netsh advfirewall show allprofiles")
        if rc != 0:
            logger.warning(
                f"[{self.name}] 'netsh advfirewall show allprofiles' "
                f"returned rc={rc}"
            )
            return False

        # Expect at least one "State" line; all must say "OFF"
        state_lines = [
            line.strip()
            for line in stdout.splitlines()
            if line.strip().lower().startswith("state")
        ]

        if not state_lines:
            logger.warning(f"[{self.name}] No 'State' lines found in netsh output")
            return False

        return all("off" in line.lower() for line in state_lines)

    def apply(self) -> None:
        """Turn off Windows Firewall on all profiles."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        rc = run_command("netsh advfirewall set allprofiles state off")
        if rc != 0:
            raise OsConfigActionError(
                f"{self.name}: 'netsh advfirewall set allprofiles state off' "
                f"returned rc={rc}"
            )

        logger.debug(f"[{self.name}] Firewall disabled on all profiles")
        self._log_apply_done()

    def revert(self) -> None:
        """Re-enable Windows Firewall on all profiles."""
        self._log_revert_start()

        rc = run_command("netsh advfirewall set allprofiles state on")
        if rc != 0:
            logger.warning(
                f"[{self.name}] 'netsh advfirewall set allprofiles state on' "
                f"returned rc={rc}"
            )
        else:
            logger.debug(f"[{self.name}] Firewall re-enabled on all profiles")

        self._log_revert_done()
