"""
OsConfig — McAfeeTasksAction

Disables McAfee scheduled tasks when McAfee is pre-installed on the SUT.

Covered task names (full path under ``\\McAfee\\``)::

    \\McAfee\\McAfee Auto Maintenance Task Agent
    \\McAfee\\DAD.WPS.Execute.Updates

If McAfee is not installed (no matching tasks found), ``apply()`` is a
no-op and ``check()`` returns ``True`` (nothing to disable).

Commands per task::

    apply()  → schtasks /Change /TN "<path>" /DISABLE
    revert() → schtasks /Change /TN "<path>" /ENABLE
    check()  → schtasks /Query /TN "<path>" /FO LIST → parse "Status: Disabled"
"""

from __future__ import annotations

import sys
import os
from typing import Optional, Dict, Any, List

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

_TASK_NAMES: List[str] = [
    r"\McAfee\McAfee Auto Maintenance Task Agent",
    r"\McAfee\DAD.WPS.Execute.Updates",
]
_CAP_KEY  = "mcafee_tasks"
_SNAP_KEY = "mcafee_tasks_disabled"


def _task_exists(task_name: str) -> bool:
    """Return ``True`` if *task_name* is present in Task Scheduler."""
    rc, _, _ = run_command_with_output(
        f'schtasks /Query /TN "{task_name}" /FO LIST'
    )
    return rc == 0


def _is_task_disabled(task_name: str) -> bool:
    """Return ``True`` when *task_name* reports Status: Disabled."""
    rc, stdout, _ = run_command_with_output(
        f'schtasks /Query /TN "{task_name}" /FO LIST'
    )
    if rc != 0:
        return True  # task not found → treat as not requiring disable
    return "disabled" in stdout.lower()


class McAfeeTasksAction(AbstractOsAction):
    """
    Disable McAfee scheduled tasks when McAfee is pre-installed.

    Handles two known McAfee task names; tasks that are not present on
    the system are silently skipped.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "McAfeeTasksAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """
        Return ``True`` when every present McAfee task is Disabled
        (or no McAfee tasks exist).
        """
        present = [t for t in _TASK_NAMES if _task_exists(t)]
        if not present:
            return True
        return all(_is_task_disabled(t) for t in present)

    def apply(self) -> None:
        """Disable all present McAfee tasks."""
        self._log_apply_start()

        present = [t for t in _TASK_NAMES if _task_exists(t)]
        if not present:
            logger.debug(f"[{self.name}] No McAfee tasks found — skipping")
            self._log_apply_skip()
            return

        disabled: List[str] = []
        errors: List[str] = []

        for task in present:
            if _is_task_disabled(task):
                logger.debug(f"[{self.name}] Already disabled: {task}")
                disabled.append(task)
                continue
            rc = run_command(f'schtasks /Change /TN "{task}" /DISABLE')
            if rc != 0:
                errors.append(f"{task} (rc={rc})")
                logger.warning(f"[{self.name}] Failed to disable: {task} (rc={rc})")
            else:
                logger.debug(f"[{self.name}] Disabled: {task}")
                disabled.append(task)

        self._save_snapshot(_SNAP_KEY, disabled)

        if errors:
            raise OsConfigActionError(
                f"{self.name}: failed to disable task(s): {', '.join(errors)}"
            )

        self._log_apply_done()

    def revert(self) -> None:
        """Re-enable all tasks that were disabled by ``apply()``."""
        self._log_revert_start()

        tasks: List[str] = self._load_snapshot(_SNAP_KEY, default=[])
        if not tasks:
            logger.debug(f"[{self.name}] No snapshot — nothing to revert")
            self._log_revert_done()
            return

        for task in tasks:
            rc = run_command(f'schtasks /Change /TN "{task}" /ENABLE')
            if rc != 0:
                logger.warning(f"[{self.name}] Failed to re-enable: {task} (rc={rc})")
            else:
                logger.debug(f"[{self.name}] Re-enabled: {task}")

        self._log_revert_done()
