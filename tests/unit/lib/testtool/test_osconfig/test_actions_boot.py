"""
Unit tests for Phase 4 boot actions.

All subprocess and registry calls are fully mocked.
Tests: TestSigningAction, RecoveryAction, AutoRebootAction,
       AutoAdminLogonAction, MemoryDumpAction
"""

import pytest
from unittest.mock import patch, call, MagicMock

from lib.testtool.osconfig.actions.test_signing import TestSigningAction
from lib.testtool.osconfig.actions.recovery import RecoveryAction
from lib.testtool.osconfig.actions.auto_reboot import AutoRebootAction
from lib.testtool.osconfig.actions.auto_admin_logon import AutoAdminLogonAction
from lib.testtool.osconfig.actions.memory_dump import MemoryDumpAction
from lib.testtool.osconfig.exceptions import OsConfigActionError

_TS  = "lib.testtool.osconfig.actions.test_signing"
_REC = "lib.testtool.osconfig.actions.recovery"
_AR  = "lib.testtool.osconfig.actions.auto_reboot"
_AL  = "lib.testtool.osconfig.actions.auto_admin_logon"
_MD  = "lib.testtool.osconfig.actions.memory_dump"


# ============================================================================
# TestSigningAction
# ============================================================================

class TestTestSigningActionAttributes:
    def test_name(self):
        assert TestSigningAction().name == "TestSigningAction"

    def test_supported_on_win10(self, win10_build):
        assert TestSigningAction.supported_on(win10_build) is True


class TestTestSigningActionCheck:

    @patch(f"{_TS}.run_command_with_output",
           return_value=(0, "testsigning                Yes", ""))
    def test_check_true_when_yes(self, mock_cmd):
        assert TestSigningAction().check() is True

    @patch(f"{_TS}.run_command_with_output",
           return_value=(0, "testsigning                No", ""))
    def test_check_false_when_no(self, mock_cmd):
        assert TestSigningAction().check() is False

    @patch(f"{_TS}.run_command_with_output",
           return_value=(0, "bootstatuspolicy           IgnoreAllFailures", ""))
    def test_check_false_when_no_testsigning_line(self, mock_cmd):
        assert TestSigningAction().check() is False

    @patch(f"{_TS}.run_command_with_output", return_value=(1, "", "error"))
    def test_check_false_on_bcdedit_failure(self, mock_cmd):
        assert TestSigningAction().check() is False


class TestTestSigningActionApply:

    @patch(f"{_TS}.run_command", return_value=0)
    @patch(f"{_TS}.run_command_with_output",
           return_value=(0, "bootstatuspolicy  IgnoreAllFailures", ""))
    def test_apply_calls_bcdedit_on(self, mock_q, mock_cmd):
        TestSigningAction().apply()
        mock_cmd.assert_called_once()
        assert "testsigning on" in mock_cmd.call_args[0][0]

    @patch(f"{_TS}.run_command", return_value=1)
    @patch(f"{_TS}.run_command_with_output",
           return_value=(0, "bootstatuspolicy  IgnoreAllFailures", ""))
    def test_apply_raises_on_failure(self, mock_q, mock_cmd):
        with pytest.raises(OsConfigActionError):
            TestSigningAction().apply()

    @patch(f"{_TS}.run_command", return_value=0)
    @patch(f"{_TS}.run_command_with_output",
           return_value=(0, "testsigning   Yes", ""))
    def test_apply_skips_when_already_on(self, mock_q, mock_cmd):
        TestSigningAction().apply()
        mock_cmd.assert_not_called()


class TestTestSigningActionRevert:

    @patch(f"{_TS}.run_command", return_value=0)
    def test_revert_calls_bcdedit_off(self, mock_cmd):
        TestSigningAction().revert()
        assert "testsigning off" in mock_cmd.call_args[0][0]

    @patch(f"{_TS}.run_command", return_value=1)
    def test_revert_does_not_raise_on_failure(self, mock_cmd):
        TestSigningAction().revert()   # no exception


# ============================================================================
# RecoveryAction
# ============================================================================

class TestRecoveryActionCheck:

    @patch(f"{_REC}.run_command_with_output",
           return_value=(0, "recoveryenabled            No", ""))
    def test_check_true_when_no(self, mock_cmd):
        assert RecoveryAction().check() is True

    @patch(f"{_REC}.run_command_with_output",
           return_value=(0, "recoveryenabled            Yes", ""))
    def test_check_false_when_yes(self, mock_cmd):
        assert RecoveryAction().check() is False

    @patch(f"{_REC}.run_command_with_output",
           return_value=(0, "bootstatuspolicy data only", ""))
    def test_check_false_when_no_recovery_line(self, mock_cmd):
        assert RecoveryAction().check() is False


class TestRecoveryActionApply:

    @patch(f"{_REC}.run_command", return_value=0)
    @patch(f"{_REC}.run_command_with_output",
           return_value=(0, "bootstatuspolicy data", ""))
    def test_apply_calls_bcdedit_disable(self, mock_q, mock_cmd):
        RecoveryAction().apply()
        mock_cmd.assert_called_once()
        assert "recoveryenabled No" in mock_cmd.call_args[0][0]

    @patch(f"{_REC}.run_command", return_value=1)
    @patch(f"{_REC}.run_command_with_output",
           return_value=(0, "bootstatuspolicy data", ""))
    def test_apply_raises_on_failure(self, mock_q, mock_cmd):
        with pytest.raises(OsConfigActionError):
            RecoveryAction().apply()


class TestRecoveryActionRevert:

    @patch(f"{_REC}.run_command", return_value=0)
    def test_revert_calls_bcdedit_enable(self, mock_cmd):
        RecoveryAction().revert()
        assert "recoveryenabled Yes" in mock_cmd.call_args[0][0]


# ============================================================================
# AutoRebootAction
# ============================================================================

class TestAutoRebootActionCheck:

    @patch(f"{_AR}.read_value_safe", return_value=0)
    def test_check_true_when_zero(self, mock_reg):
        assert AutoRebootAction().check() is True

    @patch(f"{_AR}.read_value_safe", return_value=1)
    def test_check_false_when_one(self, mock_reg):
        assert AutoRebootAction().check() is False

    @patch(f"{_AR}.read_value_safe", return_value=None)
    def test_check_false_when_absent(self, mock_reg):
        assert AutoRebootAction().check() is False


class TestAutoRebootActionApply:

    @patch(f"{_AR}.write_value")
    @patch(f"{_AR}.read_value_safe", return_value=1)
    def test_apply_writes_zero(self, mock_reg, mock_write):
        AutoRebootAction().apply()
        mock_write.assert_called_once()
        assert mock_write.call_args[0][3] == 0

    @patch(f"{_AR}.write_value")
    @patch(f"{_AR}.read_value_safe", return_value=0)
    def test_apply_skips_when_disabled(self, mock_reg, mock_write):
        AutoRebootAction().apply()
        mock_write.assert_not_called()

    @patch(f"{_AR}.write_value")
    @patch(f"{_AR}.read_value_safe", return_value=1)
    def test_apply_saves_snapshot(self, mock_reg, mock_write):
        action = AutoRebootAction()
        action.apply()
        assert action._snapshot.get("auto_reboot_orig") == 1


class TestAutoRebootActionRevert:

    @patch(f"{_AR}.write_value")
    def test_revert_restores_original(self, mock_write):
        action = AutoRebootAction()
        action._snapshot["auto_reboot_orig"] = 1
        action.revert()
        assert mock_write.call_args[0][3] == 1

    @patch(f"{_AR}.write_value")
    def test_revert_defaults_to_one(self, mock_write):
        AutoRebootAction().revert()
        assert mock_write.call_args[0][3] == 1


# ============================================================================
# AutoAdminLogonAction
# ============================================================================

class TestAutoAdminLogonActionCheck:

    @patch(f"{_AL}.read_value_safe", return_value="1")
    def test_check_true_when_one(self, mock_reg):
        assert AutoAdminLogonAction().check() is True

    @patch(f"{_AL}.read_value_safe", return_value="0")
    def test_check_false_when_zero(self, mock_reg):
        assert AutoAdminLogonAction().check() is False

    @patch(f"{_AL}.read_value_safe", return_value=None)
    def test_check_false_when_absent(self, mock_reg):
        assert AutoAdminLogonAction().check() is False


class TestAutoAdminLogonActionApply:

    @patch(f"{_AL}.write_value")
    @patch(f"{_AL}.read_value_safe", return_value="0")
    def test_apply_writes_one(self, mock_reg, mock_write):
        AutoAdminLogonAction().apply()
        assert mock_write.call_args[0][3] == "1"

    @patch(f"{_AL}.write_value")
    @patch(f"{_AL}.read_value_safe", return_value="1")
    def test_apply_skips_when_enabled(self, mock_reg, mock_write):
        AutoAdminLogonAction().apply()
        mock_write.assert_not_called()

    @patch(f"{_AL}.write_value")
    @patch(f"{_AL}.read_value_safe", return_value="0")
    def test_apply_saves_snapshot(self, mock_reg, mock_write):
        action = AutoAdminLogonAction()
        action.apply()
        assert action._snapshot.get("auto_admin_logon_orig") == "0"


class TestAutoAdminLogonActionRevert:

    @patch(f"{_AL}.write_value")
    def test_revert_restores_to_zero(self, mock_write):
        action = AutoAdminLogonAction()
        action._snapshot["auto_admin_logon_orig"] = "0"
        action.revert()
        assert mock_write.call_args[0][3] == "0"

    @patch(f"{_AL}.write_value")
    def test_revert_defaults_to_zero_string(self, mock_write):
        AutoAdminLogonAction().revert()
        assert mock_write.call_args[0][3] == "0"


# ============================================================================
# MemoryDumpAction
# ============================================================================

class TestMemoryDumpActionCheck:

    @patch(f"{_MD}.read_value_safe", return_value=3)
    def test_check_true_when_small_dump(self, mock_reg):
        assert MemoryDumpAction().check() is True

    @patch(f"{_MD}.read_value_safe", return_value=2)
    def test_check_false_when_kernel_dump(self, mock_reg):
        assert MemoryDumpAction().check() is False

    @patch(f"{_MD}.read_value_safe", return_value=None)
    def test_check_false_when_absent(self, mock_reg):
        assert MemoryDumpAction().check() is False


class TestMemoryDumpActionApply:

    @patch(f"{_MD}.write_value")
    @patch(f"{_MD}.read_value_safe", return_value=7)  # Automatic
    def test_apply_writes_small_dump(self, mock_reg, mock_write):
        MemoryDumpAction().apply()
        written = [c[0][3] for c in mock_write.call_args_list]
        assert 3 in written   # CrashDumpEnabled = 3

    @patch(f"{_MD}.write_value")
    @patch(f"{_MD}.read_value_safe", return_value=3)  # already small
    def test_apply_skips_when_done(self, mock_reg, mock_write):
        MemoryDumpAction().apply()
        mock_write.assert_not_called()

    @patch(f"{_MD}.write_value")
    @patch(f"{_MD}.read_value_safe", return_value=7)
    def test_apply_saves_snapshot(self, mock_reg, mock_write):
        action = MemoryDumpAction()
        action.apply()
        assert action._snapshot.get("memory_dump_type_orig") == 7


class TestMemoryDumpActionRevert:

    @patch(f"{_MD}.write_value")
    def test_revert_restores_original(self, mock_write):
        action = MemoryDumpAction()
        action._snapshot["memory_dump_type_orig"] = 7
        action.revert()
        assert mock_write.call_args[0][3] == 7

    @patch(f"{_MD}.write_value")
    def test_revert_defaults_to_auto_dump(self, mock_write):
        MemoryDumpAction().revert()
        assert mock_write.call_args[0][3] == 7
