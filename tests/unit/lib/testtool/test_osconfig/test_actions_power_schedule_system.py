"""
Unit tests for Phase 4 power, schedule, and system actions.

All subprocess, registry, and filesystem calls are fully mocked.
Tests: PowerPlanAction, PowerTimeoutAction, HibernationAction,
       UnattendedSleepAction, DefragScheduleAction,
       DefenderScanScheduleAction, SystemRestoreAction,
       FastStartupAction, NotificationAction, CortanaAction,
       BackgroundAppsAction, PagefileAction
"""

import pytest
from unittest.mock import patch, call, MagicMock

from lib.testtool.osconfig.actions.power_plan import PowerPlanAction
from lib.testtool.osconfig.actions.power_timeout import PowerTimeoutAction
from lib.testtool.osconfig.actions.hibernation import HibernationAction, UnattendedSleepAction
from lib.testtool.osconfig.actions.defrag_schedule import DefragScheduleAction
from lib.testtool.osconfig.actions.defender_scan_schedule import DefenderScanScheduleAction
from lib.testtool.osconfig.actions.system_restore import SystemRestoreAction
from lib.testtool.osconfig.actions.fast_startup import FastStartupAction
from lib.testtool.osconfig.actions.notifications import NotificationAction
from lib.testtool.osconfig.actions.cortana import CortanaAction
from lib.testtool.osconfig.actions.background_apps import BackgroundAppsAction
from lib.testtool.osconfig.actions.pagefile import PagefileAction
from lib.testtool.osconfig.exceptions import OsConfigActionError

_PP   = "lib.testtool.osconfig.actions.power_plan"
_PT   = "lib.testtool.osconfig.actions.power_timeout"
_HIB  = "lib.testtool.osconfig.actions.hibernation"
_DEF  = "lib.testtool.osconfig.actions.defrag_schedule"
_DSS  = "lib.testtool.osconfig.actions.defender_scan_schedule"
_SR   = "lib.testtool.osconfig.actions.system_restore"
_FS   = "lib.testtool.osconfig.actions.fast_startup"
_NOT  = "lib.testtool.osconfig.actions.notifications"
_COR  = "lib.testtool.osconfig.actions.cortana"
_BGA  = "lib.testtool.osconfig.actions.background_apps"
_PF   = "lib.testtool.osconfig.actions.pagefile"

# Known Windows plan GUIDs
_GUID_BALANCED  = "381b4222-f694-41f0-9685-ff5bb260df2e"
_GUID_HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
_GUID_SAVER     = "a1841308-3541-4fab-bc81-f71556f20b4a"

# Snapshot key (matches power_plan.py _SNAP_SCHEME)
_SNAP_SCHEME = "power_plan_orig_guid"


# ============================================================================
# PowerPlanAction
# ============================================================================

class TestPowerPlanActionValidation:

    def test_invalid_plan_name_raises(self):
        with pytest.raises(ValueError, match="Unknown power plan"):
            PowerPlanAction("turbo_mode")

    def test_valid_plans_do_not_raise(self):
        for plan in ("balanced", "high_performance", "power_saver"):
            PowerPlanAction(plan)   # must not raise


class TestPowerPlanActionCheck:

    @patch(f"{_PP}.run_command_with_output",
           return_value=(0, f"Power Scheme GUID: {_GUID_HIGH_PERF}  (High performance)", ""))
    def test_check_true_when_active(self, mock_cmd):
        assert PowerPlanAction("high_performance").check() is True

    @patch(f"{_PP}.run_command_with_output",
           return_value=(0, f"Power Scheme GUID: {_GUID_BALANCED}  (Balanced)", ""))
    def test_check_false_when_different(self, mock_cmd):
        assert PowerPlanAction("high_performance").check() is False

    @patch(f"{_PP}.run_command_with_output", return_value=(1, "", "error"))
    def test_check_false_on_failure(self, mock_cmd):
        assert PowerPlanAction("balanced").check() is False


class TestPowerPlanActionApply:

    @patch(f"{_PP}.run_command", return_value=0)
    @patch(f"{_PP}.run_command_with_output",
           return_value=(0, f"Power Scheme GUID: {_GUID_BALANCED}  (Balanced)", ""))
    def test_apply_calls_setactive(self, mock_q, mock_cmd):
        PowerPlanAction("high_performance").apply()
        cmd = mock_cmd.call_args[0][0]
        assert "setactive" in cmd
        assert _GUID_HIGH_PERF in cmd

    @patch(f"{_PP}.run_command", return_value=1)
    @patch(f"{_PP}.run_command_with_output",
           return_value=(0, f"Power Scheme GUID: {_GUID_BALANCED}  (Balanced)", ""))
    def test_apply_raises_on_failure(self, mock_q, mock_cmd):
        with pytest.raises(OsConfigActionError):
            PowerPlanAction("high_performance").apply()

    @patch(f"{_PP}.run_command", return_value=0)
    @patch(f"{_PP}.run_command_with_output",
           return_value=(0, f"Power Scheme GUID: {_GUID_BALANCED}  (Balanced)", ""))
    def test_apply_saves_original_guid(self, mock_q, mock_cmd):
        action = PowerPlanAction("high_performance")
        action.apply()
        assert action._snapshot.get("power_plan_orig_guid") == _GUID_BALANCED

    @patch(f"{_PP}.run_command", return_value=0)
    @patch(f"{_PP}.run_command_with_output",
           return_value=(0, f"Power Scheme GUID: {_GUID_HIGH_PERF}  (High performance)", ""))
    def test_apply_skips_when_already_active(self, mock_q, mock_cmd):
        PowerPlanAction("high_performance").apply()
        mock_cmd.assert_not_called()


class TestPowerPlanActionRevert:

    @patch(f"{_PP}.run_command", return_value=0)
    def test_revert_restores_snapshot_guid(self, mock_cmd):
        action = PowerPlanAction("high_performance")
        action._snapshot["power_plan_orig_guid"] = _GUID_BALANCED
        action.revert()
        cmd = mock_cmd.call_args[0][0]
        assert _GUID_BALANCED in cmd

    @patch(f"{_PP}.run_command", return_value=0)
    def test_revert_defaults_to_balanced(self, mock_cmd):
        action = PowerPlanAction("high_performance")
        action._snapshot[_SNAP_SCHEME] = _GUID_BALANCED
        action.revert()
        cmd = mock_cmd.call_args[0][0]
        assert _GUID_BALANCED in cmd


# ============================================================================
# PowerTimeoutAction
# ============================================================================

class TestPowerTimeoutActionValidation:

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown timeout_type"):
            PowerTimeoutAction("brightness")

    def test_valid_types(self):
        for t in ("monitor", "standby", "hibernate", "disk"):
            PowerTimeoutAction(t)

    def test_name_includes_type(self):
        assert "monitor" in PowerTimeoutAction("monitor").name


class TestPowerTimeoutActionCheck:

    def test_check_always_false(self):
        for t in ("monitor", "standby", "hibernate", "disk"):
            assert PowerTimeoutAction(t).check() is False


class TestPowerTimeoutActionApply:

    @patch(f"{_PT}.run_command", return_value=0)
    def test_apply_sets_ac_and_dc_to_zero(self, mock_cmd):
        PowerTimeoutAction("monitor").apply()
        calls = [c[0][0] for c in mock_cmd.call_args_list]
        # Expect two calls (AC and DC) both setting to 0
        assert len(calls) == 2
        assert all("0" in c for c in calls)

    @patch(f"{_PT}.run_command", return_value=1)
    def test_apply_raises_on_failure(self, mock_cmd):
        with pytest.raises(OsConfigActionError):
            PowerTimeoutAction("standby").apply()


class TestPowerTimeoutActionRevert:

    @patch(f"{_PT}.run_command", return_value=0)
    def test_revert_uses_saved_snapshot(self, mock_cmd):
        action = PowerTimeoutAction("monitor")
        action._snapshot["power_timeout_monitor_ac_orig"] = 600
        action._snapshot["power_timeout_monitor_dc_orig"] = 300
        action.revert()
        calls = [c[0][0] for c in mock_cmd.call_args_list]
        assert any("600" in c for c in calls)
        assert any("300" in c for c in calls)

    @patch(f"{_PT}.run_command", return_value=0)
    def test_revert_defaults_monitor_to_900(self, mock_cmd):
        PowerTimeoutAction("monitor").revert()
        calls = [c[0][0] for c in mock_cmd.call_args_list]
        assert any("900" in c for c in calls)

    @patch(f"{_PT}.run_command", return_value=0)
    def test_revert_defaults_hibernate_to_zero(self, mock_cmd):
        PowerTimeoutAction("hibernate").revert()
        calls = [c[0][0] for c in mock_cmd.call_args_list]
        assert all("0" in c for c in calls)


# ============================================================================
# HibernationAction
# ============================================================================

class TestHibernationActionCheck:

    @patch(f"{_HIB}.os.path.exists", return_value=False)
    def test_check_true_when_hiberfil_absent(self, mock_exists):
        assert HibernationAction().check() is True

    @patch(f"{_HIB}.os.path.exists", return_value=True)
    def test_check_false_when_hiberfil_present(self, mock_exists):
        assert HibernationAction().check() is False


class TestHibernationActionApply:

    @patch(f"{_HIB}.run_command", return_value=0)
    @patch(f"{_HIB}.os.path.exists", return_value=True)
    def test_apply_calls_powercfg_off(self, mock_ex, mock_cmd):
        HibernationAction().apply()
        assert "hibernate off" in mock_cmd.call_args[0][0]

    @patch(f"{_HIB}.os.path.exists", return_value=False)
    def test_apply_skips_when_already_off(self, mock_ex):
        with patch(f"{_HIB}.run_command", return_value=0) as mock_cmd:
            HibernationAction().apply()
            mock_cmd.assert_not_called()


class TestHibernationActionRevert:

    @patch(f"{_HIB}.run_command", return_value=0)
    def test_revert_calls_powercfg_on(self, mock_cmd):
        HibernationAction().revert()
        assert "hibernate on" in mock_cmd.call_args[0][0]


# ============================================================================
# UnattendedSleepAction
# ============================================================================

class TestUnattendedSleepActionCheck:

    def test_check_always_false(self):
        assert UnattendedSleepAction().check() is False


class TestUnattendedSleepActionApply:

    @patch(f"{_HIB}.run_command", return_value=0)
    def test_apply_issues_setacvalueindex(self, mock_cmd):
        UnattendedSleepAction().apply()
        calls = [c[0][0] for c in mock_cmd.call_args_list]
        assert any("setacvalueindex" in c for c in calls)

    @patch(f"{_HIB}.run_command", return_value=1)
    def test_apply_raises_on_failure(self, mock_cmd):
        with pytest.raises(OsConfigActionError):
            UnattendedSleepAction().apply()


class TestUnattendedSleepActionRevert:

    @patch(f"{_HIB}.run_command", return_value=0)
    def test_revert_issues_setacvalueindex(self, mock_cmd):
        action = UnattendedSleepAction()
        action._snapshot["unattended_sleep_ac_orig"] = 1200
        action.revert()
        calls = [c[0][0] for c in mock_cmd.call_args_list]
        assert any("setacvalueindex" in c for c in calls)


# ============================================================================
# DefragScheduleAction
# ============================================================================

class TestDefragScheduleActionCheck:

    @patch(f"{_DEF}.run_command_with_output",
           return_value=(0, "Status:                    Disabled", ""))
    def test_check_true_when_disabled(self, mock_cmd):
        assert DefragScheduleAction().check() is True

    @patch(f"{_DEF}.run_command_with_output",
           return_value=(0, "Status:                    Ready", ""))
    def test_check_false_when_ready(self, mock_cmd):
        assert DefragScheduleAction().check() is False

    @patch(f"{_DEF}.run_command_with_output", return_value=(1, "", "error"))
    def test_check_false_on_failure(self, mock_cmd):
        assert DefragScheduleAction().check() is False


class TestDefragScheduleActionApply:

    @patch(f"{_DEF}.run_command", return_value=0)
    @patch(f"{_DEF}.run_command_with_output",
           return_value=(0, "Status:                    Ready", ""))
    def test_apply_calls_schtasks_disable(self, mock_q, mock_cmd):
        DefragScheduleAction().apply()
        args = mock_cmd.call_args[0][0]
        assert "/DISABLE" in args

    @patch(f"{_DEF}.run_command_with_output",
           return_value=(0, "Status:                    Disabled", ""))
    def test_apply_skips_when_already_disabled(self, mock_q):
        with patch(f"{_DEF}.run_command", return_value=0) as mock_cmd:
            DefragScheduleAction().apply()
            mock_cmd.assert_not_called()

    @patch(f"{_DEF}.run_command", return_value=1)
    @patch(f"{_DEF}.run_command_with_output",
           return_value=(0, "Status:                    Ready", ""))
    def test_apply_raises_on_failure(self, mock_q, mock_cmd):
        with pytest.raises(OsConfigActionError):
            DefragScheduleAction().apply()


class TestDefragScheduleActionRevert:

    @patch(f"{_DEF}.run_command", return_value=0)
    def test_revert_calls_schtasks_enable(self, mock_cmd):
        DefragScheduleAction().revert()
        args = mock_cmd.call_args[0][0]
        assert "/ENABLE" in args


# ============================================================================
# DefenderScanScheduleAction
# ============================================================================

class TestDefenderScanScheduleActionCheck:

    @patch(f"{_DSS}.run_command_with_output",
           return_value=(0, "Status:                    Disabled", ""))
    def test_check_true_when_disabled(self, mock_cmd):
        assert DefenderScanScheduleAction().check() is True

    @patch(f"{_DSS}.run_command_with_output",
           return_value=(0, "Status:                    Ready", ""))
    def test_check_false_when_enabled(self, mock_cmd):
        assert DefenderScanScheduleAction().check() is False


class TestDefenderScanScheduleActionApply:

    @patch(f"{_DSS}.run_command", return_value=0)
    @patch(f"{_DSS}.run_command_with_output",
           return_value=(0, "Status:                    Ready", ""))
    def test_apply_disables_defender_scan(self, mock_q, mock_cmd):
        DefenderScanScheduleAction().apply()
        args = mock_cmd.call_args[0][0]
        assert "Windows Defender" in args
        assert "/DISABLE" in args

    @patch(f"{_DSS}.run_command", return_value=0)
    @patch(f"{_DSS}.run_command_with_output",
           return_value=(0, "Status:                    Disabled", ""))
    def test_apply_skips_when_disabled(self, mock_q, mock_cmd):
        DefenderScanScheduleAction().apply()
        mock_cmd.assert_not_called()


class TestDefenderScanScheduleActionRevert:

    @patch(f"{_DSS}.run_command", return_value=0)
    def test_revert_enables_scan(self, mock_cmd):
        DefenderScanScheduleAction().revert()
        assert "/ENABLE" in mock_cmd.call_args[0][0]


# ============================================================================
# SystemRestoreAction
# ============================================================================

class TestSystemRestoreActionSupport:

    def test_not_supported_on_server(self, win_server_build):
        assert SystemRestoreAction.supported_on(win_server_build) is False

    def test_supported_on_win10(self, win10_build):
        assert SystemRestoreAction.supported_on(win10_build) is True


class TestSystemRestoreActionCheck:

    @patch(f"{_SR}.read_value_safe", return_value=1)
    def test_check_true_when_disabled(self, mock_reg):
        assert SystemRestoreAction().check() is True

    @patch(f"{_SR}.read_value_safe", return_value=0)
    def test_check_false_when_enabled(self, mock_reg):
        assert SystemRestoreAction().check() is False


class TestSystemRestoreActionApply:

    @patch(f"{_SR}.run_powershell", return_value=0)
    @patch(f"{_SR}.write_value")
    @patch(f"{_SR}.read_value_safe", return_value=0)
    def test_apply_calls_powershell_and_registry(self, mock_reg, mock_write, mock_ps):
        SystemRestoreAction().apply()
        mock_ps.assert_called_once()
        mock_write.assert_called_once()
        assert mock_write.call_args[0][3] == 1

    @patch(f"{_SR}.read_value_safe", return_value=1)
    def test_apply_skips_when_already_disabled(self, mock_reg):
        with patch(f"{_SR}.run_powershell") as mock_ps, \
             patch(f"{_SR}.write_value") as mock_write:
            SystemRestoreAction().apply()
            mock_ps.assert_not_called()
            mock_write.assert_not_called()


class TestSystemRestoreActionRevert:

    @patch(f"{_SR}.run_powershell", return_value=0)
    @patch(f"{_SR}.write_value")
    def test_revert_enables_restore(self, mock_write, mock_ps):
        action = SystemRestoreAction()
        action._snapshot["system_restore_sr_orig"] = 0
        action.revert()
        assert mock_write.call_args[0][3] == 0


# ============================================================================
# FastStartupAction
# ============================================================================

class TestFastStartupActionCheck:

    @patch(f"{_FS}.read_value_safe", return_value=0)
    def test_check_true_when_disabled(self, mock_reg):
        assert FastStartupAction().check() is True

    @patch(f"{_FS}.read_value_safe", return_value=1)
    def test_check_false_when_enabled(self, mock_reg):
        assert FastStartupAction().check() is False


class TestFastStartupActionApply:

    @patch(f"{_FS}.write_value")
    @patch(f"{_FS}.read_value_safe", return_value=1)
    def test_apply_writes_zero(self, mock_reg, mock_write):
        FastStartupAction().apply()
        assert mock_write.call_args[0][3] == 0

    @patch(f"{_FS}.write_value")
    @patch(f"{_FS}.read_value_safe", return_value=0)
    def test_apply_skips_when_off(self, mock_reg, mock_write):
        FastStartupAction().apply()
        mock_write.assert_not_called()


class TestFastStartupActionRevert:

    @patch(f"{_FS}.write_value")
    def test_revert_defaults_to_one(self, mock_write):
        FastStartupAction().revert()
        assert mock_write.call_args[0][3] == 1

    @patch(f"{_FS}.write_value")
    def test_revert_restores_snapshot(self, mock_write):
        action = FastStartupAction()
        action._snapshot["fast_startup_orig"] = 0
        action.revert()
        assert mock_write.call_args[0][3] == 0


# ============================================================================
# NotificationAction
# ============================================================================

class TestNotificationActionCheck:

    @patch(f"{_NOT}.read_value_safe", return_value=1)
    def test_check_true_when_disabled(self, mock_reg):
        assert NotificationAction().check() is True

    @patch(f"{_NOT}.read_value_safe", return_value=0)
    def test_check_false_when_enabled(self, mock_reg):
        assert NotificationAction().check() is False

    @patch(f"{_NOT}.read_value_safe", return_value=None)
    def test_check_false_when_absent(self, mock_reg):
        assert NotificationAction().check() is False


class TestNotificationActionApply:

    @patch(f"{_NOT}.write_value")
    @patch(f"{_NOT}.read_value_safe", return_value=None)
    def test_apply_writes_both_hives(self, mock_reg, mock_write):
        NotificationAction().apply()
        assert mock_write.call_count == 2   # HKLM + HKCU

    @patch(f"{_NOT}.write_value")
    @patch(f"{_NOT}.read_value_safe", return_value=1)
    def test_apply_skips_when_done(self, mock_reg, mock_write):
        NotificationAction().apply()
        mock_write.assert_not_called()


class TestNotificationActionRevert:

    @patch(f"{_NOT}.delete_value")
    @patch(f"{_NOT}.write_value")
    def test_revert_restores_absent_by_deleting(self, mock_write, mock_del):
        action = NotificationAction()
        action._snapshot["notifications_hklm_orig"] = None
        action._snapshot["notifications_hkcu_orig"] = None
        action.revert()
        assert mock_del.call_count == 2
        mock_write.assert_not_called()

    @patch(f"{_NOT}.delete_value")
    @patch(f"{_NOT}.write_value")
    def test_revert_writes_when_had_value(self, mock_write, mock_del):
        action = NotificationAction()
        action._snapshot["notifications_hklm_orig"] = 0
        action._snapshot["notifications_hkcu_orig"] = 0
        action.revert()
        assert mock_write.call_count == 2


# ============================================================================
# CortanaAction
# ============================================================================

class TestCortanaActionCheck:

    @patch(f"{_COR}.read_value_safe", return_value=0)
    def test_check_true_when_disabled(self, mock_reg):
        assert CortanaAction().check() is True

    @patch(f"{_COR}.read_value_safe", return_value=1)
    def test_check_false_when_enabled(self, mock_reg):
        assert CortanaAction().check() is False


class TestCortanaActionApply:

    @patch(f"{_COR}.write_value")
    @patch(f"{_COR}.read_value_safe", return_value=1)
    def test_apply_writes_zero(self, mock_reg, mock_write):
        CortanaAction().apply()
        assert mock_write.call_args[0][3] == 0

    @patch(f"{_COR}.write_value")
    @patch(f"{_COR}.read_value_safe", return_value=1)
    def test_apply_saves_original(self, mock_reg, mock_write):
        action = CortanaAction()
        action.apply()
        assert action._snapshot.get("cortana_orig") == 1


class TestCortanaActionRevert:

    @patch(f"{_COR}.delete_value")
    @patch(f"{_COR}.write_value")
    def test_revert_deletes_when_was_absent(self, mock_write, mock_del):
        action = CortanaAction()
        action._snapshot["cortana_orig"] = None
        action.revert()
        mock_del.assert_called_once()
        mock_write.assert_not_called()

    @patch(f"{_COR}.delete_value")
    @patch(f"{_COR}.write_value")
    def test_revert_writes_when_had_value(self, mock_write, mock_del):
        action = CortanaAction()
        action._snapshot["cortana_orig"] = 1
        action.revert()
        mock_write.assert_called_once()
        mock_del.assert_not_called()


# ============================================================================
# BackgroundAppsAction
# ============================================================================

class TestBackgroundAppsActionCheck:

    @patch(f"{_BGA}.read_value_safe", return_value=2)
    def test_check_true_when_blocked(self, mock_reg):
        assert BackgroundAppsAction().check() is True

    @patch(f"{_BGA}.read_value_safe", return_value=0)
    def test_check_false_when_allowed(self, mock_reg):
        assert BackgroundAppsAction().check() is False


class TestBackgroundAppsActionApply:

    @patch(f"{_BGA}.write_value")
    @patch(f"{_BGA}.read_value_safe", return_value=None)
    def test_apply_writes_two(self, mock_reg, mock_write):
        BackgroundAppsAction().apply()
        assert mock_write.call_args[0][3] == 2

    @patch(f"{_BGA}.write_value")
    @patch(f"{_BGA}.read_value_safe", return_value=2)
    def test_apply_skips_when_blocked(self, mock_reg, mock_write):
        BackgroundAppsAction().apply()
        mock_write.assert_not_called()


class TestBackgroundAppsActionRevert:

    @patch(f"{_BGA}.delete_value")
    @patch(f"{_BGA}.write_value")
    def test_revert_deletes_when_was_absent(self, mock_write, mock_del):
        action = BackgroundAppsAction()
        action._snapshot["background_apps_orig"] = None
        action.revert()
        mock_del.assert_called_once()

    @patch(f"{_BGA}.delete_value")
    @patch(f"{_BGA}.write_value")
    def test_revert_writes_when_had_value(self, mock_write, mock_del):
        action = BackgroundAppsAction()
        action._snapshot["background_apps_orig"] = 0
        action.revert()
        mock_write.assert_called_once()


# ============================================================================
# PagefileAction
# ============================================================================

class TestPagefileActionDefaults:

    def test_default_drive_is_c(self):
        pf = PagefileAction()
        assert pf._drive == "C:"

    def test_custom_params(self):
        pf = PagefileAction(drive="D:", min_mb=2048, max_mb=4096)
        assert pf._drive == "D:"
        assert pf._min_mb == 2048
        assert pf._max_mb == 4096

    def test_name(self):
        assert PagefileAction().name == "PagefileAction"


class TestPagefileActionCheck:

    @patch(f"{_PF}.read_value_safe", side_effect=[0, ["C:\\pagefile.sys 4096 8192"]])
    def test_check_true_when_manual_and_correct(self, mock_reg):
        assert PagefileAction().check() is True

    @patch(f"{_PF}.read_value_safe", side_effect=[1, []])
    def test_check_false_when_auto(self, mock_reg):
        assert PagefileAction().check() is False

    @patch(f"{_PF}.read_value_safe", side_effect=[0, []])
    def test_check_false_when_manual_but_no_entry(self, mock_reg):
        assert PagefileAction().check() is False


class TestPagefileActionApply:

    @patch(f"{_PF}.write_value")
    @patch(f"{_PF}.read_value_safe", side_effect=[1, [], 1, []])
    def test_apply_writes_auto_and_paging_files(self, mock_reg, mock_write):
        PagefileAction().apply()
        assert mock_write.call_count == 2

    @patch(f"{_PF}.write_value")
    @patch(f"{_PF}.read_value_safe", side_effect=[0, ["C:\\pagefile.sys 4096 8192"]])
    def test_apply_skips_when_already_set(self, mock_reg, mock_write):
        PagefileAction().apply()
        mock_write.assert_not_called()

    @patch(f"{_PF}.write_value")
    @patch(f"{_PF}.read_value_safe", side_effect=[1, [], 1, []])
    def test_apply_saves_snapshot(self, mock_reg, mock_write):
        action = PagefileAction()
        action.apply()
        assert "pagefile_auto_orig" in action._snapshot


class TestPagefileActionRevert:

    @patch(f"{_PF}.write_value")
    def test_revert_restores_auto_managed(self, mock_write):
        action = PagefileAction()
        action._snapshot["pagefile_auto_orig"] = 1
        action.revert()
        # AutomaticManagedPagefile must be restored to 1
        assert any(c[0][3] == 1 for c in mock_write.call_args_list)

    @patch(f"{_PF}.write_value")
    def test_revert_defaults_to_auto_when_no_snapshot(self, mock_write):
        PagefileAction().revert()
        assert any(c[0][3] == 1 for c in mock_write.call_args_list)
