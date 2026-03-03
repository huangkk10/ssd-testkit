"""
OsConfig — TestSigningAction

Enables Windows Test Signing Mode via ``bcdedit``, which allows loading
kernel-mode drivers that are not signed by a trusted certificate authority.

Commands used::

    apply()  → bcdedit /set testsigning on
    revert() → bcdedit /set testsigning off
    check()  → bcdedit /enum {current}  (parse "testsigning" field)

⚠️  Requires reboot to take effect and Administrator privileges.

Mirrors ``enable_test_mode()`` in Common.py.
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

_CAP_KEY = "test_signing"


class TestSigningAction(AbstractOsAction):
    """
    Enable Windows Test Signing Mode (``bcdedit /set testsigning on``).

    Allows unsigned kernel-mode drivers to load.  Requires a reboot.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "TestSigningAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    # ------------------------------------------------------------------ #
    # AbstractOsAction interface                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        """Available on all supported Windows builds."""
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``testsigning`` is ``Yes`` in the current BCD entry."""
        rc, stdout, _ = run_command_with_output("bcdedit /enum {current}")
        if rc != 0:
            logger.warning(
                f"[{self.name}] 'bcdedit /enum {{current}}' returned rc={rc}"
            )
            return False
        for line in stdout.splitlines():
            stripped = line.strip().lower()
            if stripped.startswith("testsigning"):
                return "yes" in stripped
        # Line not present → testsigning is off (default)
        return False

    def apply(self) -> None:
        """Enable Test Signing Mode."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        rc = run_command("bcdedit /set testsigning on")
        if rc != 0:
            raise OsConfigActionError(
                f"{self.name}: 'bcdedit /set testsigning on' returned rc={rc}"
            )

        logger.debug(f"[{self.name}] Test Signing enabled (reboot required)")
        self._log_apply_done()

    def revert(self) -> None:
        """Disable Test Signing Mode."""
        self._log_revert_start()

        rc = run_command("bcdedit /set testsigning off")
        if rc != 0:
            logger.warning(
                f"[{self.name}] 'bcdedit /set testsigning off' returned rc={rc}"
            )
        else:
            logger.debug(f"[{self.name}] Test Signing disabled")

        self._log_revert_done()
