"""
OsConfig — OneDriveTasksAction

Disables OneDrive-related scheduled tasks matched by name prefix.
This supplements :class:`~lib.testtool.osconfig.actions.onedrive.OneDriveAction`
(which only sets Group Policy registry keys) by also stopping the tasks that
wake the system during Modern Standby.

Covered task prefixes
---------------------
* ``OneDrive Reporting Task``         — usage telemetry (SID-suffixed)
* ``OneDrive Standalone Update Task`` — standalone-build auto-updater (SID-suffixed)
* ``OneDrive Startup Task``           — auto-start at logon (SID-suffixed)

Example task names observed in the field::

    OneDrive Reporting Task-S-1-5-21-1697851942-2560724758-894526796-1001
    OneDrive Reporting Task-S-1-5-21-1697851942-2560724758-894526796-500
    OneDrive Standalone Update Task-S-1-5-21-...-1001
    OneDrive Startup Task-S-1-5-21-...-500

Because the SID suffix differs per account the action uses a prefix search
(``schtasks /Query /FO CSV /NH``) and disables every match.

Commands per matched task::

    apply()  → schtasks /Change /TN "<task>" /DISABLE
    revert() → schtasks /Change /TN "<task>" /ENABLE
    check()  → all matching tasks report Status: Disabled (or no tasks exist)

If OneDrive is not installed, ``apply()`` is a no-op and ``check()`` returns
``True``.
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

_PREFIXES: List[str] = [
    "OneDrive Reporting Task",
    "OneDrive Standalone Update Task",
    "OneDrive Startup Task",
]
_CAP_KEY  = "onedrive_tasks"
_SNAP_KEY = "onedrive_tasks_disabled"


def _is_task_disabled(task_name: str) -> bool:
    """Return ``True`` when *task_name* reports Status: Disabled."""
    rc, stdout, _ = run_command_with_output(
        f'schtasks /Query /TN "{task_name}" /FO LIST'
    )
    if rc != 0:
        return True  # task not found → treat as not requiring disable
    return "disabled" in stdout.lower()


def _collect_tasks() -> List[str]:
    """Return all OneDrive task names matching any of the defined prefixes."""
    found: List[str] = []
    for prefix in _PREFIXES:
        found.extend(query_tasks_by_prefix(prefix))
    return found


class OneDriveTasksAction(AbstractOsAction):
    """
    Disable all OneDrive scheduled tasks (Reporting, Standalone Update, Startup).

    Finds tasks by prefix match so that SID-suffixed variants (``-1001``,
    ``-500``, etc.) are captured automatically regardless of the local user
    account SIDs.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "OneDriveTasksAction"

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
        Return ``True`` when every matching OneDrive task is Disabled
        (or no tasks exist).
        """
        candidates = _collect_tasks()
        if not candidates:
            return True
        return all(_is_task_disabled(t) for t in candidates)

    def apply(self) -> None:
        """Disable all matching OneDrive scheduled tasks."""
        self._log_apply_start()

        candidates = _collect_tasks()
        if not candidates:
            logger.debug(f"[{self.name}] No OneDrive tasks found — skipping")
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

        # Persist for revert
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
