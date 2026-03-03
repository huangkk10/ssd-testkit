"""
Integration tests — Boot Actions (registry-only, safe).

Tests AutoRebootAction and MemoryDumpAction which touch only registry keys
under HKLM\\SYSTEM\\CurrentControlSet\\Control\\CrashControl.
Both take effect immediately for new crashes; no reboot needed to revert.

⚠️ Excluded (require reboot):
    - TestSigningAction  (bcdedit change only live after reboot)
    - RecoveryAction     (bcdedit change only live after reboot)
    - AutoAdminLogonAction (logon-time registry, safe to test but cosmetic)
"""

import pytest

from lib.testtool.osconfig.actions.auto_reboot import AutoRebootAction
from lib.testtool.osconfig.actions.memory_dump import MemoryDumpAction
from lib.testtool.osconfig.actions.auto_admin_logon import AutoAdminLogonAction

pytestmark = [pytest.mark.integration, pytest.mark.admin]


class TestAutoRebootIntegration:

    def test_apply_check_revert(self, build_info):
        if not AutoRebootAction.supported_on(build_info):
            pytest.skip()

        action = AutoRebootAction()
        try:
            action.apply()
            assert action.check() is True, (
                "AutoRebootAction.check() False immediately after apply()"
            )
        finally:
            action.revert()

        assert action.check() is False, (
            "AutoRebootAction.check() still True after revert()"
        )

    def test_apply_idempotent(self, build_info):
        if not AutoRebootAction.supported_on(build_info):
            pytest.skip()
        action = AutoRebootAction()
        try:
            action.apply()
            action.apply()   # must not raise
            assert action.check() is True
        finally:
            action.revert()


class TestMemoryDumpIntegration:

    def test_apply_sets_small_dump(self, build_info):
        if not MemoryDumpAction.supported_on(build_info):
            pytest.skip()

        action = MemoryDumpAction()
        try:
            action.apply()
            assert action.check() is True, (
                "MemoryDumpAction.check() False immediately after apply()"
            )
        finally:
            action.revert()

    def test_revert_restores_original(self, build_info):
        if not MemoryDumpAction.supported_on(build_info):
            pytest.skip()

        action = MemoryDumpAction()
        try:
            action.apply()
        finally:
            action.revert()

        assert action.check() is False, (
            "MemoryDumpAction.check() still True after revert()"
        )


class TestAutoAdminLogonIntegration:
    """Test only apply/revert cycle; does not validate actual logon behaviour."""

    def test_apply_check_revert(self, build_info):
        if not AutoAdminLogonAction.supported_on(build_info):
            pytest.skip()

        action = AutoAdminLogonAction()
        try:
            action.apply()
            assert action.check() is True
        finally:
            action.revert()

        assert action.check() is False
