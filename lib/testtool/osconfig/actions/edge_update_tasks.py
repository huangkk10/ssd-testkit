"""
OsConfig — EdgeUpdateTasksAction

Disables all Microsoft Edge Update scheduled tasks whose name begins with
``MicrosoftEdgeUpdateTaskMachine``.  This covers both variants observed in
the field::

    MicrosoftEdgeUpdateTaskMachineCore{GUID}
    MicrosoftEdgeUpdateTaskMachineUA{GUID}

Because the GUID suffix varies between installations the action uses a
prefix search (``schtasks /Query /FO CSV /NH``) rather than a hard-coded
task name.

Commands per matched task::

    apply()  → schtasks /Change /TN "<task>" /DISABLE
    revert() → schtasks /Change /TN "<task>" /ENABLE
    check()  → schtasks /Query /TN "<task>" /FO LIST → parse "Status: Disabled"

If Edge is not installed (no matching tasks), ``apply()`` is a no-op and
``check()`` returns ``True`` (nothing to disable).
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
from ._helpers import run_command, run_command_with_output, query_tasks_by_prefix

logger = get_module_logger(__name__)

_PREFIX  = "MicrosoftEdgeUpdateTaskMachine"
_CAP_KEY = "edge_update_tasks"
_SNAP_KEY = "edge_tasks_disabled"


def _is_task_disabled(task_name: str) -> bool:
    """Return ``True`` when *task_name* reports Status: Disabled."""
    rc, stdout, _ = run_command_with_output(
        f'schtasks /Query /TN "{task_name}" /FO LIST'
    )
    if rc != 0:
        return True  # task not found → treat as not requiring disable
    return "disabled" in stdout.lower()


class EdgeUpdateTasksAction(AbstractOsAction):
    """
    Disable all Microsoft Edge Update scheduled tasks (Machine-scope).

    Finds tasks by prefix match on ``MicrosoftEdgeUpdateTaskMachine`` so
    the action is resilient to GUID suffix variations between Edge versions.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "EdgeUpdateTasksAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    # ------------------------------------------------------------------ #
    # AbstractOsAction interface                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """
        Return ``True`` when every matching Edge Update task is Disabled
        (or no tasks exist).
        """
        candidates: List[str] = query_tasks_by_prefix(_PREFIX)
        if not candidates:
            return True
        return all(_is_task_disabled(t) for t in candidates)

    def apply(self) -> None:
        """Disable all matching Edge Update tasks."""
        self._log_apply_start()

        candidates: List[str] = query_tasks_by_prefix(_PREFIX)
        if not candidates:
            logger.debug(f"[{self.name}] No Edge Update tasks found — skipping")
            self._log_apply_skip()
            return

        disabled: List[str] = []
        errors: List[str] = []

        for task in candidates:
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

        # Persist the list that was found (whether already disabled or just disabled)
        # so revert() knows which tasks to restore.
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
