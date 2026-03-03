"""
OsConfig — PowerPlanAction

Sets the active Windows power plan via ``powercfg``.

Supported plan names and their GUIDs::

    balanced          → 381b4222-f694-41f0-9685-ff5bb260df2e
    high_performance  → 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
    power_saver       → a1841308-3541-4fab-bc81-f71556f20b4a

``check()`` queries the currently active scheme and compares its GUID.
``revert()`` restores the scheme GUID that was active before ``apply()``.

Mirrors ``enable_power_*_mode()`` in Common.py.
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

_CAP_KEY = "power_plan"

_PLAN_GUIDS: Dict[str, str] = {
    "balanced":         "381b4222-f694-41f0-9685-ff5bb260df2e",
    "high_performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
    "power_saver":      "a1841308-3541-4fab-bc81-f71556f20b4a",
}

_SNAP_SCHEME = "power_plan_orig_guid"


def _get_active_scheme_guid() -> Optional[str]:
    """Return the GUID of the currently active power scheme, or ``None``."""
    rc, stdout, _ = run_command_with_output("powercfg /getactivescheme")
    if rc != 0:
        return None
    # Line: "Power Scheme GUID: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  (High performance)"
    m = re.search(
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        stdout, re.IGNORECASE,
    )
    return m.group(1).lower() if m else None


class PowerPlanAction(AbstractOsAction):
    """
    Activate the specified Windows power plan.

    Args:
        plan:           One of ``"balanced"``, ``"high_performance"``,
                        ``"power_saver"``.  Default: ``"high_performance"``.
        snapshot_store: Optional shared snapshot dict.

    Raises:
        ValueError: If *plan* is not one of the recognised plan names.
    """

    name = "PowerPlanAction"

    def __init__(
        self,
        plan: str = "high_performance",
        snapshot_store: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(snapshot_store)
        if plan not in _PLAN_GUIDS:
            raise ValueError(
                f"Unknown power plan {plan!r}. "
                f"Valid values: {list(_PLAN_GUIDS)}"
            )
        self._plan = plan
        self._target_guid = _PLAN_GUIDS[plan]

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when the active power scheme matches the target GUID."""
        active = _get_active_scheme_guid()
        if active is None:
            return False
        return active.lower() == self._target_guid.lower()

    def apply(self) -> None:
        """Activate the configured power plan."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        # Snapshot current scheme
        orig_guid = _get_active_scheme_guid()
        self._save_snapshot(_SNAP_SCHEME, orig_guid)
        logger.debug(f"[{self.name}] snapshot: active_scheme={orig_guid}")

        rc = run_command(f"powercfg /setactive {self._target_guid}")
        if rc != 0:
            raise OsConfigActionError(
                f"{self.name}: 'powercfg /setactive {self._target_guid}' "
                f"returned rc={rc}"
            )

        logger.debug(f"[{self.name}] Power plan set to {self._plan!r}")
        self._log_apply_done()

    def revert(self) -> None:
        """Restore the previously active power plan."""
        self._log_revert_start()

        orig_guid = self._load_snapshot(_SNAP_SCHEME, default=None)
        if orig_guid is None:
            logger.warning(f"[{self.name}] No snapshot – cannot revert power plan")
            self._log_revert_done()
            return

        rc = run_command(f"powercfg /setactive {orig_guid}")
        if rc != 0:
            logger.warning(
                f"[{self.name}] 'powercfg /setactive {orig_guid}' returned rc={rc}"
            )
        else:
            logger.debug(f"[{self.name}] Power plan restored to {orig_guid}")

        self._log_revert_done()
