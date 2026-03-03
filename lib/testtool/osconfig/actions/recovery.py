"""
OsConfig — RecoveryAction

Disables the Windows Recovery Environment (WinRE) boot option via
``bcdedit``.  When disabled, the system will not automatically boot into
Recovery mode after a crash.

Commands used::

    apply()  → bcdedit /set {current} recoveryenabled No
    revert() → bcdedit /set {current} recoveryenabled Yes
    check()  → bcdedit /enum {current}  (parse "recoveryenabled" field)

Mirrors ``disable_recovery_mode()`` in Common.py.
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

_CAP_KEY = "recovery"


class RecoveryAction(AbstractOsAction):
    """
    Disable Windows Recovery Environment via ``bcdedit``.

    Prevents automatic boot into Recovery mode after a failure.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "RecoveryAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``recoveryenabled`` is ``No``."""
        rc, stdout, _ = run_command_with_output("bcdedit /enum {current}")
        if rc != 0:
            logger.warning(f"[{self.name}] bcdedit returned rc={rc}")
            return False
        for line in stdout.splitlines():
            stripped = line.strip().lower()
            if stripped.startswith("recoveryenabled"):
                return "no" in stripped
        # Line absent → recovery is enabled by default
        return False

    def apply(self) -> None:
        """Disable Recovery Environment."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        rc = run_command("bcdedit /set {current} recoveryenabled No")
        if rc != 0:
            raise OsConfigActionError(
                f"{self.name}: bcdedit returned rc={rc}"
            )

        logger.debug(f"[{self.name}] Recovery disabled")
        self._log_apply_done()

    def revert(self) -> None:
        """Re-enable Recovery Environment."""
        self._log_revert_start()

        rc = run_command("bcdedit /set {current} recoveryenabled Yes")
        if rc != 0:
            logger.warning(f"[{self.name}] bcdedit revert returned rc={rc}")
        else:
            logger.debug(f"[{self.name}] Recovery re-enabled")

        self._log_revert_done()
