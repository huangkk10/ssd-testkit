"""
OsConfig — EnableRtcWakeAction

Sets ``Allow wake timers = Enabled`` (RTCWAKE=2) on both AC and DC power
sources in the active power plan.

Background
----------
The Windows power-plan "Allow wake timers" setting (powercfg alias RTCWAKE)
controls which processes are permitted to register an RTC wake alarm that
wakes the machine from S3/S4 sleep/hibernate states.

Values:
    0 = Disable          — no wake timers allowed
    1 = Important only   — only Windows-internal timers allowed (DEFAULT on
                           many OEM builds)
    2 = Enabled          — **any** process can register a wake timer

WAC BPFS (Boot Performance Fast Startup) uses ``FAS.exe`` which calls the
Windows API (e.g. ``SetSystemWakeupAlarmTime``) to set an RTC alarm before
issuing ``shutdown /h``.  On machines where RTCWAKE=1 (Important only), this
alarm is silently dropped by the kernel, leaving the machine in S4 hibernate
with no timer to wake it.  The machine then requires a manual power press.

Setting RTCWAKE=2 ensures FAS.exe's wake timer is always honoured.

powercfg changes
----------------
    apply:  powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 2
            powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 2
            powercfg /setactive SCHEME_CURRENT
    revert: restore AC/DC to snapshotted values
    check:  powercfg /query SCHEME_CURRENT SUB_SLEEP RTCWAKE
"""

from __future__ import annotations

import sys
import os
import re
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

_CAP_KEY = "rtc_wake"
_SNAP_AC  = "rtc_wake_ac_orig"
_SNAP_DC  = "rtc_wake_dc_orig"

# Target value: 2 = Enabled (allow ANY wake timer)
_TARGET = 2


def _query_rtcwake() -> tuple[int, int]:
    """Return (ac_value, dc_value) of RTCWAKE in the current plan.

    Returns (-1, -1) if the query fails.
    """
    rc, stdout, _ = run_command_with_output(
        "powercfg /query SCHEME_CURRENT SUB_SLEEP RTCWAKE"
    )
    if rc != 0:
        return -1, -1

    ac = dc = -1
    for line in stdout.splitlines():
        line = line.strip()
        m = re.search(r"Current AC Power Setting Index:\s*(0x[0-9a-fA-F]+)", line)
        if m:
            ac = int(m.group(1), 16)
        m = re.search(r"Current DC Power Setting Index:\s*(0x[0-9a-fA-F]+)", line)
        if m:
            dc = int(m.group(1), 16)
    return ac, dc


class EnableRtcWakeAction(AbstractOsAction):
    """
    Set ``Allow wake timers = Enabled`` (RTCWAKE=2, AC and DC).

    Required before WAC BPFS assessment on machines where the default
    RTCWAKE value is 1 (Important only).  With RTCWAKE=1, FAS.exe's
    RTC wake alarm is silently ignored by the kernel, causing the machine
    to remain in S4 hibernate indefinitely after each training iteration.

    ``revert()`` restores the original AC/DC values.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "EnableRtcWakeAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when both AC and DC RTCWAKE are already 2."""
        ac, dc = _query_rtcwake()
        if ac == -1:
            return False
        return ac == _TARGET and dc == _TARGET

    def apply(self) -> None:
        """Set RTCWAKE = 2 (Enabled) on both AC and DC in the current power plan."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        ac, dc = _query_rtcwake()
        self._save_snapshot(_SNAP_AC, ac)
        self._save_snapshot(_SNAP_DC, dc)
        logger.debug(f"[{self.name}] snapshot: RTCWAKE ac={ac} dc={dc}")

        for subcmd in (
            f"powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE {_TARGET}",
            f"powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE {_TARGET}",
            "powercfg /setactive SCHEME_CURRENT",
        ):
            rc = run_command(subcmd)
            if rc != 0:
                raise OsConfigActionError(
                    f"{self.name}: '{subcmd}' returned rc={rc}"
                )

        logger.info(
            f"[{self.name}] RTCWAKE set to {_TARGET} (Enabled) on AC+DC. "
            f"Allows FAS.exe to register RTC wake alarms for BPFS training iterations."
        )
        self._log_apply_done()

    def revert(self) -> None:
        """Restore RTCWAKE to its pre-apply values."""
        self._log_revert_start()

        ac = self._load_snapshot(_SNAP_AC, default=1)
        dc = self._load_snapshot(_SNAP_DC, default=1)

        for subcmd in (
            f"powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE {ac}",
            f"powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE {dc}",
            "powercfg /setactive SCHEME_CURRENT",
        ):
            rc = run_command(subcmd)
            if rc != 0:
                logger.warning(f"[{self.name}] '{subcmd}' returned rc={rc}")

        logger.debug(f"[{self.name}] RTCWAKE restored to ac={ac} dc={dc}")
        self._log_revert_done()
