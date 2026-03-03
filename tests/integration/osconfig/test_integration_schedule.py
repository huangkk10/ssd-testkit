"""
Integration tests — Schedule Actions.

Tests DefragScheduleAction and DefenderScanScheduleAction on a real machine.
Both are immediately reversible (no reboot required).
"""

import subprocess
import pytest

from lib.testtool.osconfig.actions.defrag_schedule import DefragScheduleAction
from lib.testtool.osconfig.actions.defender_scan_schedule import DefenderScanScheduleAction

pytestmark = [pytest.mark.integration, pytest.mark.admin]


def _task_status(task_name: str) -> str:
    """Return 'disabled' or 'ready' for a scheduled task."""
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST"],
            capture_output=True, text=True, timeout=15,
        )
        output = result.stdout.lower()
        if "disabled" in output:
            return "disabled"
        return "ready"
    except Exception:
        return "unknown"


_DEFRAG_TN  = r"\Microsoft\Windows\Defrag\ScheduledDefrag"
_DEFENDER_TN = r"\Microsoft\Windows\Windows Defender\Windows Defender Scheduled Scan"


class TestDefragScheduleIntegration:

    def test_apply_check_revert(self, build_info):
        if not DefragScheduleAction.supported_on(build_info):
            pytest.skip("DefragScheduleAction not supported")

        action = DefragScheduleAction()
        before = _task_status(_DEFRAG_TN)
        try:
            action.apply()
            assert action.check() is True
            assert _task_status(_DEFRAG_TN) == "disabled"
        finally:
            action.revert()

        after = _task_status(_DEFRAG_TN)
        assert after == before or after == "ready"

    def test_apply_idempotent(self, build_info):
        if not DefragScheduleAction.supported_on(build_info):
            pytest.skip("DefragScheduleAction not supported")

        action = DefragScheduleAction()
        try:
            action.apply()
            action.apply()   # second apply must not raise
            assert action.check() is True
        finally:
            action.revert()


class TestDefenderScanScheduleIntegration:

    def test_apply_check_revert(self, build_info):
        if not DefenderScanScheduleAction.supported_on(build_info):
            pytest.skip("DefenderScanScheduleAction not supported")

        action = DefenderScanScheduleAction()
        before = _task_status(_DEFENDER_TN)
        try:
            action.apply()
            assert action.check() is True
        finally:
            action.revert()

        after = _task_status(_DEFENDER_TN)
        assert after == before or after == "ready"
