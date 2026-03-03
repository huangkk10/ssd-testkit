"""
OsConfig — DefenderScanScheduleAction

Disables the Windows Defender scheduled quick-scan task via ``schtasks``.

Task path: ``\\Microsoft\\Windows\\Windows Defender\\Windows Defender Scheduled Scan``

Commands::

    apply()  → schtasks /Change /TN "<task>" /DISABLE
    revert() → schtasks /Change /TN "<task>" /ENABLE
    check()  → schtasks /Query /TN "<task>" /FO LIST → parse "Status" for "Disabled"
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

_TASK_NAME = r"\Microsoft\Windows\Windows Defender\Windows Defender Scheduled Scan"
_CAP_KEY   = "defender_scan_schedule"


def _query_task_disabled(task_name: str) -> bool:
    rc, stdout, _ = run_command_with_output(
        f'schtasks /Query /TN "{task_name}" /FO LIST'
    )
    if rc != 0:
        return False
    return "disabled" in stdout.lower()


class DefenderScanScheduleAction(AbstractOsAction):
    """
    Disable the Windows Defender Scheduled Scan task.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "DefenderScanScheduleAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        return _query_task_disabled(_TASK_NAME)

    def apply(self) -> None:
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        rc = run_command(f'schtasks /Change /TN "{_TASK_NAME}" /DISABLE')
        if rc != 0:
            raise OsConfigActionError(
                f"{self.name}: schtasks /DISABLE returned rc={rc}"
            )

        logger.debug(f"[{self.name}] Defender Scheduled Scan disabled")
        self._log_apply_done()

    def revert(self) -> None:
        self._log_revert_start()

        rc = run_command(f'schtasks /Change /TN "{_TASK_NAME}" /ENABLE')
        if rc != 0:
            logger.warning(f"[{self.name}] schtasks /ENABLE returned rc={rc}")
        else:
            logger.debug(f"[{self.name}] Defender Scheduled Scan re-enabled")

        self._log_revert_done()
