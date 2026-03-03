"""
OsConfig — PowerTimeoutAction

Disables power-management timeouts (monitor off, standby, hibernate, disk
spindown) by setting them to 0 (never) on both AC and DC power sources.

Uses ``powercfg /change`` sub-commands::

    monitor-timeout-ac   / monitor-timeout-dc
    standby-timeout-ac   / standby-timeout-dc
    hibernate-timeout-ac / hibernate-timeout-dc
    disk-timeout-ac      / disk-timeout-dc

Each ``PowerTimeoutAction`` instance operates on a single *timeout_type*.
To disable all timeouts create four instances:

    actions = [
        PowerTimeoutAction("monitor"),
        PowerTimeoutAction("standby"),
        PowerTimeoutAction("hibernate"),
        PowerTimeoutAction("disk"),
    ]

Mirrors ``disable_power_plan_settings_*_monitor/standby/hibernate/disk()``
in Common.py.
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

_CAP_KEY = "monitor_timeout"

_VALID_TYPES = ("monitor", "standby", "hibernate", "disk")

# powercfg /change sub-command names
_SUBCOMMAND: Dict[str, Dict[str, str]] = {
    "monitor":   {"ac": "monitor-timeout-ac",   "dc": "monitor-timeout-dc"},
    "standby":   {"ac": "standby-timeout-ac",   "dc": "standby-timeout-dc"},
    "hibernate": {"ac": "hibernate-timeout-ac", "dc": "hibernate-timeout-dc"},
    "disk":      {"ac": "disk-timeout-ac",      "dc": "disk-timeout-dc"},
}

# powercfg /query field names (used by check() to read current values)
_QUERY_GUID: Dict[str, Dict[str, str]] = {
    "monitor":   {
        "ac": "SUB_VIDEO,ACSettingIndex",
        "dc": "SUB_VIDEO,DCSettingIndex",
    },
    "standby":   {
        "ac": "SUB_SLEEP,ACSettingIndex",
        "dc": "SUB_SLEEP,DCSettingIndex",
    },
    "hibernate":  {
        "ac": "SUB_SLEEP,ACSettingIndex",
        "dc": "SUB_SLEEP,DCSettingIndex",
    },
    "disk":      {
        "ac": "SUB_DISK,ACSettingIndex",
        "dc": "SUB_DISK,DCSettingIndex",
    },
}

_SNAP_AC = "power_timeout_{type}_ac_orig"
_SNAP_DC = "power_timeout_{type}_dc_orig"


def _parse_powercfg_value(stdout: str) -> Optional[int]:
    """
    Extract a decimal integer value from ``powercfg /query`` output.

    Looks for lines containing ``Current AC Power Setting Index: 0x...`` or
    ``Current DC Power Setting Index: 0x...``.

    Returns ``None`` if not found.
    """
    import re
    m = re.search(r"Current\s+(?:AC|DC)\s+Power Setting Index:\s+0x([0-9a-fA-F]+)", stdout)
    if m:
        return int(m.group(1), 16)
    return None


class PowerTimeoutAction(AbstractOsAction):
    """
    Disable a single power-management timeout (AC and DC) by setting it to 0.

    Args:
        timeout_type:   One of ``"monitor"``, ``"standby"``, ``"hibernate"``,
                        ``"disk"``.
        snapshot_store: Optional shared snapshot dict.

    Raises:
        ValueError: If *timeout_type* is not valid.
    """

    name = "PowerTimeoutAction"

    def __init__(
        self,
        timeout_type: str = "monitor",
        snapshot_store: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(snapshot_store)
        if timeout_type not in _VALID_TYPES:
            raise ValueError(
                f"Unknown timeout_type {timeout_type!r}. "
                f"Valid values: {_VALID_TYPES}"
            )
        self._type = timeout_type
        self.name = f"PowerTimeoutAction[{timeout_type}]"

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """
        Return ``True`` when both AC and DC timeout values are 0 (never).

        Uses ``powercfg /change`` to query – simplified check by attempting to
        read via ``powercfg /getactivescheme`` and comparing; for reliability
        we just try both set commands and treat success as already-set.
        Since this cannot read via a simple registry path reliably, ``check()``
        always returns ``False`` to ensure the setting is applied.  The
        idempotent behaviour is guaranteed by powercfg accepting and silently
        succeeding repeated set-to-zero operations.
        """
        # powercfg /change always succeeds for value 0; treat apply as idempotent
        return False

    def apply(self) -> None:
        """Set AC and DC timeouts to 0 (never)."""
        self._log_apply_start()

        sc = _SUBCOMMAND[self._type]
        for side, subcmd in sc.items():
            # Snapshot by reading current value via powercfg query (best effort)
            snap_key = f"power_timeout_{self._type}_{side}_orig"
            rc_q, out_q, _ = run_command_with_output(
                f"powercfg /query SCHEME_CURRENT"
            )
            orig_val = _parse_powercfg_value(out_q) if rc_q == 0 else None
            self._save_snapshot(snap_key, orig_val)

            rc = run_command(f"powercfg /change {subcmd} 0")
            if rc != 0:
                raise OsConfigActionError(
                    f"{self.name}: 'powercfg /change {subcmd} 0' returned rc={rc}"
                )
            logger.debug(f"[{self.name}] {subcmd}=0")

        self._log_apply_done()

    def revert(self) -> None:
        """
        Attempt to revert timeouts.

        If a snapshot value was captured, restores it; otherwise sets to the
        Windows default (15 minutes = 900 seconds for monitor/standby, 0 for
        hibernate/disk which are typically already 0 on desktop builds).
        """
        self._log_revert_start()

        sc = _SUBCOMMAND[self._type]
        defaults = {"monitor": 900, "standby": 900, "hibernate": 0, "disk": 0}

        for side, subcmd in sc.items():
            snap_key = f"power_timeout_{self._type}_{side}_orig"
            orig = self._load_snapshot(snap_key, default=None)
            val = int(orig) if orig is not None else defaults[self._type]
            rc = run_command(f"powercfg /change {subcmd} {val}")
            if rc != 0:
                logger.warning(
                    f"[{self.name}] revert 'powercfg /change {subcmd} {val}' "
                    f"returned rc={rc}"
                )
            else:
                logger.debug(f"[{self.name}] {subcmd} restored to {val}")

        self._log_revert_done()
