"""
OsConfig — UnattendedSleepAction + HibernationAction

Two related power-management actions:

**UnattendedSleepAction**
    Disables the unattended sleep timeout via registry (the timeout used when
    the system is idle and unattended workstation lock is active).

    Registry path::

        HKLM\\SYSTEM\\CurrentControlSet\\Control\\Power\\PowerSettings
            \\238C9FA8-0AAD-41ED-83F4-97BE242C8F20
            \\7bc4a2f9-d8fc-4469-b07b-33eb785aaca0
                Attributes = 2  (hide from UI / use registry directly)

    Simpler approach (mirrors Common.py)::

        powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP
            UNATTENDED_SLEEP_TIMEOUT 0
        powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP
            UNATTENDED_SLEEP_TIMEOUT 0

**HibernationAction**
    Enables or disables the Windows hibernation feature (hiberfil.sys) via
    ``powercfg /hibernate``.

    Commands::

        apply()  → powercfg /hibernate off
        revert() → powercfg /hibernate on
        check()  → check if hiberfil.sys exists in %SystemRoot%
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


# ---------------------------------------------------------------------------
# UnattendedSleepAction
# ---------------------------------------------------------------------------

_CAP_UNATTENDED = "unattended_sleep"


class UnattendedSleepAction(AbstractOsAction):
    """
    Disable Unattended Sleep timeout (AC and DC) for the current power plan.

    Uses ``powercfg /setacvalueindex`` and ``/setdcvalueindex`` to set the
    UNATTENDED_SLEEP_TIMEOUT to 0 (disabled).

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "UnattendedSleepAction"

    # GUIDs for unattended sleep timeout subgroup + setting
    _SUBGROUP = "238C9FA8-0AAD-41ED-83F4-97BE242C8F20"
    _SETTING  = "7bc4a2f9-d8fc-4469-b07b-33eb785aaca0"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_UNATTENDED, build_info)

    def check(self) -> bool:
        """Always return ``False`` – powercfg set-to-zero is idempotent."""
        return False

    def apply(self) -> None:
        """Set Unattended Sleep timeout to 0 on both AC and DC."""
        self._log_apply_start()

        for index_cmd in ("setacvalueindex", "setdcvalueindex"):
            rc = run_command(
                f"powercfg /{index_cmd} SCHEME_CURRENT "
                f"{self._SUBGROUP} {self._SETTING} 0"
            )
            if rc != 0:
                raise OsConfigActionError(
                    f"{self.name}: 'powercfg /{index_cmd} ... 0' returned rc={rc}"
                )
            logger.debug(f"[{self.name}] {index_cmd} set to 0")

        self._log_apply_done()

    def revert(self) -> None:
        """Re-enable Unattended Sleep (restore to OS default of 2 minutes = 120s)."""
        self._log_revert_start()

        for index_cmd in ("setacvalueindex", "setdcvalueindex"):
            rc = run_command(
                f"powercfg /{index_cmd} SCHEME_CURRENT "
                f"{self._SUBGROUP} {self._SETTING} 120"
            )
            if rc != 0:
                logger.warning(
                    f"[{self.name}] revert /{index_cmd} returned rc={rc}"
                )
            else:
                logger.debug(f"[{self.name}] {index_cmd} restored to 120s")

        self._log_revert_done()


# ---------------------------------------------------------------------------
# HibernationAction
# ---------------------------------------------------------------------------

_CAP_HIBERNATION = "hibernation"
_HIBERFIL = os.path.join(
    os.environ.get("SystemRoot", r"C:\Windows"), "hiberfil.sys"
)


class HibernationAction(AbstractOsAction):
    """
    Disable Windows Hibernation (``powercfg /hibernate off``).

    Removing hiberfil.sys frees disk space.  The change takes effect
    immediately without a reboot.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "HibernationAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_HIBERNATION, build_info)

    def check(self) -> bool:
        """
        Return ``True`` when hiberfil.sys does **not** exist.

        Absence of hiberfil.sys indicates hibernation is already disabled.
        """
        return not os.path.exists(_HIBERFIL)

    def apply(self) -> None:
        """Disable hibernation (``powercfg /hibernate off``)."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        rc = run_command("powercfg /hibernate off")
        if rc != 0:
            raise OsConfigActionError(
                f"{self.name}: 'powercfg /hibernate off' returned rc={rc}"
            )

        logger.debug(f"[{self.name}] Hibernation disabled")
        self._log_apply_done()

    def revert(self) -> None:
        """Re-enable hibernation (``powercfg /hibernate on``)."""
        self._log_revert_start()

        rc = run_command("powercfg /hibernate on")
        if rc != 0:
            logger.warning(
                f"[{self.name}] 'powercfg /hibernate on' returned rc={rc}"
            )
        else:
            logger.debug(f"[{self.name}] Hibernation re-enabled")

        self._log_revert_done()
