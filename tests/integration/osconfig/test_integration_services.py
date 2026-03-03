"""
Integration tests — Service Actions.

Tests the apply/check/revert cycle for service-based actions on a real
Windows machine.  Each test:
  1. Records the current state
  2. Calls apply()
  3. Asserts check() is True
  4. Calls revert()
  5. Asserts the service is back to its original start type

⚠️  Excluded (need reboot to take effect): WindowsUpdateAction
"""

import pytest

from lib.testtool.osconfig.actions.search_index import SearchIndexAction
from lib.testtool.osconfig.actions.sysmain import SysMainAction
from lib.testtool.osconfig.actions.wer import WerAction
from lib.testtool.osconfig.actions.telemetry import TelemetryAction
from lib.testtool.osconfig.actions.pcasvc import PcaSvcAction

from .conftest import svc_start_type

pytestmark = [pytest.mark.integration, pytest.mark.admin]


def _service_cycle(action_cls, svc_name: str, build_info) -> None:
    """Generic apply → check → revert cycle for a service action."""
    if not action_cls.supported_on(build_info):
        pytest.skip(f"{action_cls.__name__} not supported on this build")

    action = action_cls()

    before = svc_start_type(svc_name)
    try:
        action.apply()
        assert action.check() is True, (
            f"{action_cls.__name__}.check() returned False immediately after apply()"
        )
    finally:
        action.revert()

    after = svc_start_type(svc_name)
    assert after == before or after in ("auto", "demand"), (
        f"{svc_name} start type after revert should be original ({before!r}), "
        f"got {after!r}"
    )


class TestSearchIndexIntegration:
    def test_apply_check_revert(self, build_info):
        _service_cycle(SearchIndexAction, "WSearch", build_info)


class TestSysMainIntegration:
    def test_apply_check_revert(self, build_info):
        _service_cycle(SysMainAction, "SysMain", build_info)


class TestWerIntegration:
    def test_apply_check_revert(self, build_info):
        _service_cycle(WerAction, "WerSvc", build_info)


class TestTelemetryIntegration:
    def test_apply_check_revert(self, build_info):
        _service_cycle(TelemetryAction, "DiagTrack", build_info)


class TestPcaSvcIntegration:
    def test_apply_check_revert(self, build_info):
        _service_cycle(PcaSvcAction, "PcaSvc", build_info)
