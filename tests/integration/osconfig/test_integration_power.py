"""
Integration tests — Power Actions.

Tests PowerPlanAction and PowerTimeoutAction on a real machine.
Both are immediately reversible (no reboot required).
"""

import re
import subprocess
import pytest

from lib.testtool.osconfig.actions.power_plan import PowerPlanAction
from lib.testtool.osconfig.actions.power_timeout import PowerTimeoutAction

pytestmark = [pytest.mark.integration, pytest.mark.admin]

_GUID_BALANCED  = "381b4222-f694-41f0-9685-ff5bb260df2e"
_GUID_HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"


def _active_guid() -> str:
    """Return active power scheme GUID from powercfg."""
    out = subprocess.check_output(["powercfg", "/getactivescheme"],
                                  text=True, timeout=10)
    m = re.search(
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        out, re.IGNORECASE,
    )
    return m.group(1).lower() if m else ""


class TestPowerPlanIntegration:

    def test_apply_sets_high_performance(self, build_info):
        if not PowerPlanAction.supported_on(build_info):
            pytest.skip("PowerPlanAction not supported")

        action = PowerPlanAction("high_performance")
        orig_guid = _active_guid()
        try:
            action.apply()
            assert action.check() is True
            assert _active_guid() == _GUID_HIGH_PERF
        finally:
            action.revert()

        assert _active_guid() == orig_guid

    def test_already_high_perf_is_idempotent(self, build_info):
        if not PowerPlanAction.supported_on(build_info):
            pytest.skip("PowerPlanAction not supported")

        action = PowerPlanAction("high_performance")
        action.apply()
        try:
            # Second apply must not raise
            action2 = PowerPlanAction("high_performance")
            action2.apply()
            assert action2.check() is True
        finally:
            action.revert()


class TestPowerTimeoutIntegration:

    @pytest.mark.parametrize("timeout_type", ["monitor", "standby", "disk"])
    def test_apply_check_revert(self, timeout_type, build_info):
        if not PowerTimeoutAction.supported_on(build_info):
            pytest.skip("PowerTimeoutAction not supported")

        action = PowerTimeoutAction(timeout_type)
        try:
            action.apply()
            # check() always returns False for PowerTimeoutAction (idempotent design)
            assert action.check() is False
        finally:
            action.revert()
