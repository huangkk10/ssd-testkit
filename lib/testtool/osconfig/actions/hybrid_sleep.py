"""
OsConfig — DisableHybridSleepAction

Disables Hybrid Sleep by setting ``Allow hybrid sleep = Off`` on both AC and
DC power sources in the active power plan.

Background
----------
Hybrid Sleep combines S3 (sleep, RAM powered) with a simultaneous hibernate
file write so that data survives a power loss during sleep.  This is useful
for desktop scenarios but **conflicts with WAC BPFS (Boot Performance Fast
Startup) assessment**:

* BPFS calls ``FAS.exe`` which issues a ``shutdown /h`` (S4 hibernate) and
  sets an RTC wake timer to resume after the hibernate.
* When Hybrid Sleep is ON, Windows mixes S3 and S4 power-state bookkeeping.
  Subsequent training-iteration hibernates (iteration 2–6) can fail to have
  their RTC wake timer fire, leaving the machine in a hard-off or deep-sleep
  state that does not resume automatically.
* Result: the machine appears to have "shut down" permanently — it is
  actually hibernated but the wake timer never triggers.

Disabling Hybrid Sleep before running WAC BPFS ensures each ``shutdown /h``
uses a clean S4 hibernate state whose RTC wake timer is always honoured.

Registry / powercfg
-------------------
powercfg changes the active-plan GUID directly; no stable registry path
exists across plans.  We use ``powercfg /change`` to read/write.

    apply:  powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP 0
            powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP 0
            powercfg /setactive SCHEME_CURRENT
    revert: restore AC/DC to snapshotted values
    check:  powercfg /query SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP
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

_CAP_KEY   = "hybrid_sleep"
_SNAP_AC   = "hybrid_sleep_ac_orig"
_SNAP_DC   = "hybrid_sleep_dc_orig"


def _query_hybrid_sleep() -> tuple[int, int]:
    """Return (ac_value, dc_value) of HYBRIDSLEEP in the current plan.

    Returns (-1, -1) if the query fails.
    """
    rc, stdout, _ = run_command_with_output(
        "powercfg /query SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP"
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


class DisableHybridSleepAction(AbstractOsAction):
    """
    Disable Hybrid Sleep (``HYBRIDSLEEP = 0`` on AC and DC).

    Required before WAC BPFS (Boot Performance Fast Startup) assessment.
    With Hybrid Sleep ON, RTC wake timers fired by ``FAS.exe`` during
    training iterations 2–6 may silently fail, leaving the machine
    permanently hibernated.

    ``revert()`` restores the original AC/DC values.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "DisableHybridSleepAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when both AC and DC HYBRIDSLEEP are already 0."""
        ac, dc = _query_hybrid_sleep()
        if ac == -1:
            return False
        return ac == 0 and dc == 0

    def apply(self) -> None:
        """Set HYBRIDSLEEP = 0 on both AC and DC in the current power plan."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        ac, dc = _query_hybrid_sleep()
        self._save_snapshot(_SNAP_AC, ac)
        self._save_snapshot(_SNAP_DC, dc)
        logger.debug(f"[{self.name}] snapshot: HYBRIDSLEEP ac={ac} dc={dc}")

        for subcmd in (
            "powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP 0",
            "powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP 0",
            "powercfg /setactive SCHEME_CURRENT",
        ):
            rc = run_command(subcmd)
            if rc != 0:
                raise OsConfigActionError(
                    f"{self.name}: '{subcmd}' returned rc={rc}"
                )

        logger.info(
            f"[{self.name}] Hybrid Sleep disabled (HYBRIDSLEEP=0 AC+DC). "
            f"Fixes BPFS wake-timer failures during training iterations."
        )
        self._log_apply_done()

    def revert(self) -> None:
        """Restore HYBRIDSLEEP to its pre-apply values."""
        self._log_revert_start()

        ac = self._load_snapshot(_SNAP_AC, default=1)
        dc = self._load_snapshot(_SNAP_DC, default=1)

        for subcmd in (
            f"powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP {ac}",
            f"powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP {dc}",
            "powercfg /setactive SCHEME_CURRENT",
        ):
            rc = run_command(subcmd)
            if rc != 0:
                logger.warning(f"[{self.name}] '{subcmd}' returned rc={rc}")

        logger.debug(f"[{self.name}] HYBRIDSLEEP restored to ac={ac} dc={dc}")
        self._log_revert_done()
