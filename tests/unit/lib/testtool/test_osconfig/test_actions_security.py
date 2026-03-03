"""
Unit tests for Phase 3 security + OneDrive actions.

All subprocess, PowerShell, and registry calls are fully mocked.
Tests cover: check(), apply(), revert(), supported_on() for each action class.

Classes under test
------------------
* OneDriveAction
* DefenderAction
* MemoryIntegrityAction
* VulnDriverBlocklistAction
* FirewallAction
* UacAction
"""

import pytest
from unittest.mock import patch, call, MagicMock

from lib.testtool.osconfig.actions.onedrive import OneDriveAction
from lib.testtool.osconfig.actions.defender import DefenderAction
from lib.testtool.osconfig.actions.memory_integrity import MemoryIntegrityAction
from lib.testtool.osconfig.actions.vuln_driver_blocklist import VulnDriverBlocklistAction
from lib.testtool.osconfig.actions.firewall import FirewallAction
from lib.testtool.osconfig.actions.uac import UacAction
from lib.testtool.osconfig.exceptions import OsConfigActionError
from lib.testtool.osconfig.os_compat import WindowsBuildInfo

# Patch target namespaces
_OD   = "lib.testtool.osconfig.actions.onedrive"
_DEF  = "lib.testtool.osconfig.actions.defender"
_MI   = "lib.testtool.osconfig.actions.memory_integrity"
_VDB  = "lib.testtool.osconfig.actions.vuln_driver_blocklist"
_FW   = "lib.testtool.osconfig.actions.firewall"
_UAC  = "lib.testtool.osconfig.actions.uac"


# ============================================================================
# OneDriveAction
# ============================================================================

class TestOneDriveActionAttributes:

    def test_name(self):
        assert OneDriveAction().name == "OneDriveAction"

    def test_instantiates_with_snapshot_store(self):
        store = {}
        action = OneDriveAction(snapshot_store=store)
        assert action._snapshot is store


class TestOneDriveActionSupportedOn:

    def test_supported_on_rs1(self, win10_build):
        """Win10 22H2 (build 19045) ≥ 14393 → supported."""
        assert OneDriveAction.supported_on(win10_build) is True

    def test_supported_on_win11(self, win11_build):
        assert OneDriveAction.supported_on(win11_build) is True

    def test_not_supported_pre_rs1(self, win10_home_build):
        """Win10 Home build 10586 < 14393 → not supported."""
        assert OneDriveAction.supported_on(win10_home_build) is False


class TestOneDriveActionCheck:

    @patch(f"{_OD}.read_value_safe", return_value=1)
    def test_check_true_all_set(self, mock_reg):
        assert OneDriveAction().check() is True

    @patch(f"{_OD}.read_value_safe", return_value=0)
    def test_check_false_when_zero(self, mock_reg):
        assert OneDriveAction().check() is False

    @patch(f"{_OD}.read_value_safe", return_value=None)
    def test_check_false_when_absent(self, mock_reg):
        assert OneDriveAction().check() is False

    def test_check_false_when_one_missing(self):
        """If first two values are 1 but third is None, check returns False."""
        side_effects = [1, 1, None]
        with patch(f"{_OD}.read_value_safe", side_effect=side_effects):
            assert OneDriveAction().check() is False


class TestOneDriveActionApply:

    @patch(f"{_OD}.write_value")
    @patch(f"{_OD}.read_value_safe", return_value=None)
    def test_apply_writes_all_three_values(self, mock_read, mock_write):
        action = OneDriveAction()
        action.apply()
        assert mock_write.call_count == 3
        written_vals = [c[0][2] for c in mock_write.call_args_list]
        assert "DisableMeteredNetworkFileSync" in written_vals
        assert "DisableFileSyncNGSC" in written_vals
        assert "PreventNetworkTrafficPreUserSignIn" in written_vals

    @patch(f"{_OD}.write_value")
    @patch(f"{_OD}.read_value_safe", return_value=None)
    def test_apply_saves_snapshots(self, mock_read, mock_write):
        action = OneDriveAction()
        action.apply()
        assert "od_metered_orig" in action._snapshot
        assert "od_filesync_orig" in action._snapshot
        assert "od_prelogon_orig" in action._snapshot

    @patch(f"{_OD}.write_value")
    @patch(f"{_OD}.read_value_safe", return_value=1)   # already set
    def test_apply_skips_when_already_applied(self, mock_read, mock_write):
        action = OneDriveAction()
        action.apply()
        mock_write.assert_not_called()


class TestOneDriveActionRevert:

    @patch(f"{_OD}.delete_value")
    @patch(f"{_OD}.write_value")
    def test_revert_restores_previous_values(self, mock_write, mock_del):
        action = OneDriveAction()
        # Simulate snapshots from a previous apply
        action._snapshot["od_metered_orig"]  = 0
        action._snapshot["od_filesync_orig"] = 0
        action._snapshot["od_prelogon_orig"] = 0
        action.revert()
        assert mock_write.call_count == 3
        mock_del.assert_not_called()

    @patch(f"{_OD}.delete_value")
    @patch(f"{_OD}.write_value")
    def test_revert_deletes_absent_values(self, mock_write, mock_del):
        action = OneDriveAction()
        action._snapshot["od_metered_orig"]  = None
        action._snapshot["od_filesync_orig"] = None
        action._snapshot["od_prelogon_orig"] = None
        action.revert()
        assert mock_del.call_count == 3
        mock_write.assert_not_called()


# ============================================================================
# DefenderAction
# ============================================================================

class TestDefenderActionAttributes:

    def test_name(self):
        assert DefenderAction().name == "DefenderAction"


class TestDefenderActionSupportedOn:

    def test_supported_on_win10(self, win10_build):
        assert DefenderAction.supported_on(win10_build) is True

    def test_supported_on_win11(self, win11_build):
        assert DefenderAction.supported_on(win11_build) is True


class TestDefenderActionCheck:

    @patch(f"{_DEF}.read_value_safe", return_value=1)
    def test_check_true_when_disabled(self, mock_reg):
        assert DefenderAction().check() is True

    @patch(f"{_DEF}.read_value_safe", return_value=0)
    def test_check_false_when_zero(self, mock_reg):
        assert DefenderAction().check() is False

    @patch(f"{_DEF}.read_value_safe", return_value=None)
    def test_check_false_when_absent(self, mock_reg):
        assert DefenderAction().check() is False


class TestDefenderActionApplyPowerShellSuccess:

    @patch(f"{_DEF}.write_value")
    @patch(f"{_DEF}.run_powershell", return_value=0)   # PS succeeds
    @patch(f"{_DEF}.read_value_safe", return_value=None)
    def test_apply_calls_powershell(self, mock_reg, mock_ps, mock_write):
        DefenderAction().apply()
        mock_ps.assert_called_once()
        ps_cmd = mock_ps.call_args[0][0]
        assert "DisableRealtimeMonitoring" in ps_cmd
        assert "$true" in ps_cmd

    @patch(f"{_DEF}.write_value")
    @patch(f"{_DEF}.run_powershell", return_value=0)
    @patch(f"{_DEF}.read_value_safe", return_value=None)
    def test_apply_also_writes_registry(self, mock_reg, mock_ps, mock_write):
        """Even when PS succeeds, registry GPO is still written."""
        DefenderAction().apply()
        mock_write.assert_called_once()

    @patch(f"{_DEF}.write_value")
    @patch(f"{_DEF}.run_powershell", return_value=0)
    @patch(f"{_DEF}.read_value_safe", return_value=None)
    def test_apply_saves_ps_ok_snapshot(self, mock_reg, mock_ps, mock_write):
        action = DefenderAction()
        action.apply()
        assert action._snapshot.get("defender_ps_succeeded") is True


class TestDefenderActionApplyPowerShellFails:

    @patch(f"{_DEF}.write_value")
    @patch(f"{_DEF}.run_powershell", return_value=1)   # PS fails
    @patch(f"{_DEF}.read_value_safe", return_value=None)
    def test_apply_falls_back_to_registry(self, mock_reg, mock_ps, mock_write):
        """When PS fails, registry fallback is used; no exception raised."""
        action = DefenderAction()
        action.apply()   # should not raise
        mock_write.assert_called_once()

    @patch(f"{_DEF}.write_value")
    @patch(f"{_DEF}.run_powershell", return_value=1)
    @patch(f"{_DEF}.read_value_safe", return_value=None)
    def test_apply_saves_ps_failed_snapshot(self, mock_reg, mock_ps, mock_write):
        action = DefenderAction()
        action.apply()
        assert action._snapshot.get("defender_ps_succeeded") is False

    @patch(f"{_DEF}.write_value", side_effect=Exception("Access denied"))
    @patch(f"{_DEF}.run_powershell", return_value=1)
    @patch(f"{_DEF}.read_value_safe", return_value=None)
    def test_apply_warns_when_both_fail(self, mock_reg, mock_ps, mock_write):
        """Both PS and registry fail → no exception (fail_on_error=False default)."""
        action = DefenderAction()
        action.apply()   # should not raise

    @patch(f"{_DEF}.write_value", side_effect=Exception("Access denied"))
    @patch(f"{_DEF}.run_powershell", return_value=1)
    @patch(f"{_DEF}.read_value_safe", return_value=None)
    def test_apply_raises_when_fail_on_error(self, mock_reg, mock_ps, mock_write):
        action = DefenderAction(fail_on_error=True)
        with pytest.raises(OsConfigActionError):
            action.apply()

    @patch(f"{_DEF}.write_value")
    @patch(f"{_DEF}.run_powershell", return_value=0)
    @patch(f"{_DEF}.read_value_safe", return_value=1)  # already applied
    def test_apply_skips_when_already_applied(self, mock_reg, mock_ps, mock_write):
        action = DefenderAction()
        action.apply()
        mock_ps.assert_not_called()
        mock_write.assert_not_called()


class TestDefenderActionRevert:

    @patch(f"{_DEF}.delete_value")
    @patch(f"{_DEF}.write_value")
    @patch(f"{_DEF}.run_powershell", return_value=0)
    def test_revert_restores_registry_and_calls_ps(self, mock_ps, mock_write, mock_del):
        action = DefenderAction()
        action._snapshot["defender_disable_antispyware_orig"] = 0
        action._snapshot["defender_ps_succeeded"] = True
        action.revert()
        mock_ps.assert_called_once()
        ps_cmd = mock_ps.call_args[0][0]
        assert "$false" in ps_cmd
        mock_write.assert_called_once()

    @patch(f"{_DEF}.delete_value")
    @patch(f"{_DEF}.write_value")
    @patch(f"{_DEF}.run_powershell", return_value=0)
    def test_revert_deletes_when_reg_was_absent(self, mock_ps, mock_write, mock_del):
        action = DefenderAction()
        action._snapshot["defender_disable_antispyware_orig"] = None
        action._snapshot["defender_ps_succeeded"] = False
        action.revert()
        mock_del.assert_called_once()
        mock_write.assert_not_called()

    @patch(f"{_DEF}.delete_value")
    @patch(f"{_DEF}.write_value")
    @patch(f"{_DEF}.run_powershell", return_value=0)
    def test_revert_skips_ps_when_ps_was_not_used(self, mock_ps, mock_write, mock_del):
        action = DefenderAction()
        action._snapshot["defender_disable_antispyware_orig"] = 0
        action._snapshot["defender_ps_succeeded"] = False
        action.revert()
        mock_ps.assert_not_called()


# ============================================================================
# MemoryIntegrityAction
# ============================================================================

class TestMemoryIntegrityActionAttributes:

    def test_name(self):
        assert MemoryIntegrityAction().name == "MemoryIntegrityAction"


class TestMemoryIntegrityActionSupportedOn:

    def test_supported_win10(self, win10_build):
        assert MemoryIntegrityAction.supported_on(win10_build) is True


class TestMemoryIntegrityActionCheck:

    @patch(f"{_MI}.read_value_safe", return_value=0)
    def test_check_true_when_zero(self, mock_reg):
        assert MemoryIntegrityAction().check() is True

    @patch(f"{_MI}.read_value_safe", return_value=1)
    def test_check_false_when_one(self, mock_reg):
        assert MemoryIntegrityAction().check() is False

    @patch(f"{_MI}.read_value_safe", return_value=None)
    def test_check_true_when_absent(self, mock_reg):
        """Absent key means HVCI never explicitly enabled → treat as disabled."""
        assert MemoryIntegrityAction().check() is True


class TestMemoryIntegrityActionApply:

    @patch(f"{_MI}.write_value")
    @patch(f"{_MI}.read_value_safe", return_value=1)   # currently enabled
    def test_apply_writes_zero(self, mock_reg, mock_write):
        MemoryIntegrityAction().apply()
        mock_write.assert_called_once_with(
            "HKLM",
            r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity",
            "Enabled", 0, mock_write.call_args[0][4],
        )

    @patch(f"{_MI}.write_value")
    @patch(f"{_MI}.read_value_safe", return_value=0)   # already disabled
    def test_apply_skips_when_already_disabled(self, mock_reg, mock_write):
        MemoryIntegrityAction().apply()
        mock_write.assert_not_called()

    @patch(f"{_MI}.write_value")
    @patch(f"{_MI}.read_value_safe", return_value=1)
    def test_apply_saves_snapshot(self, mock_reg, mock_write):
        action = MemoryIntegrityAction()
        action.apply()
        assert action._snapshot.get("hvci_enabled_orig") == 1


class TestMemoryIntegrityActionRevert:

    @patch(f"{_MI}.delete_value")
    @patch(f"{_MI}.write_value")
    def test_revert_restores_value(self, mock_write, mock_del):
        action = MemoryIntegrityAction()
        action._snapshot["hvci_enabled_orig"] = 1
        action.revert()
        mock_write.assert_called_once()
        mock_del.assert_not_called()

    @patch(f"{_MI}.delete_value")
    @patch(f"{_MI}.write_value")
    def test_revert_deletes_when_absent(self, mock_write, mock_del):
        action = MemoryIntegrityAction()
        action._snapshot["hvci_enabled_orig"] = None
        action.revert()
        mock_del.assert_called_once()
        mock_write.assert_not_called()


# ============================================================================
# VulnDriverBlocklistAction
# ============================================================================

class TestVulnDriverBlocklistActionAttributes:

    def test_name(self):
        assert VulnDriverBlocklistAction().name == "VulnDriverBlocklistAction"


class TestVulnDriverBlocklistActionCheck:

    @patch(f"{_VDB}.read_value_safe", return_value=0)
    def test_check_true_when_zero(self, mock_reg):
        assert VulnDriverBlocklistAction().check() is True

    @patch(f"{_VDB}.read_value_safe", return_value=1)
    def test_check_false_when_one(self, mock_reg):
        assert VulnDriverBlocklistAction().check() is False

    @patch(f"{_VDB}.read_value_safe", return_value=None)
    def test_check_false_when_absent(self, mock_reg):
        """Absent = default enabled → not yet disabled."""
        assert VulnDriverBlocklistAction().check() is False


class TestVulnDriverBlocklistActionApply:

    @patch(f"{_VDB}.write_value")
    @patch(f"{_VDB}.read_value_safe", return_value=None)  # absent = enabled
    def test_apply_writes_zero(self, mock_reg, mock_write):
        VulnDriverBlocklistAction().apply()
        mock_write.assert_called_once()
        assert mock_write.call_args[0][3] == 0

    @patch(f"{_VDB}.write_value")
    @patch(f"{_VDB}.read_value_safe", return_value=0)   # already disabled
    def test_apply_skips_when_disabled(self, mock_reg, mock_write):
        VulnDriverBlocklistAction().apply()
        mock_write.assert_not_called()

    @patch(f"{_VDB}.write_value")
    @patch(f"{_VDB}.read_value_safe", return_value=1)
    def test_apply_saves_snapshot(self, mock_reg, mock_write):
        action = VulnDriverBlocklistAction()
        action.apply()
        assert action._snapshot.get("vuln_driver_blocklist_orig") == 1


class TestVulnDriverBlocklistActionRevert:

    @patch(f"{_VDB}.delete_value")
    @patch(f"{_VDB}.write_value")
    def test_revert_restores_value(self, mock_write, mock_del):
        action = VulnDriverBlocklistAction()
        action._snapshot["vuln_driver_blocklist_orig"] = 1
        action.revert()
        mock_write.assert_called_once()
        mock_del.assert_not_called()

    @patch(f"{_VDB}.delete_value")
    @patch(f"{_VDB}.write_value")
    def test_revert_deletes_when_absent(self, mock_write, mock_del):
        action = VulnDriverBlocklistAction()
        action._snapshot["vuln_driver_blocklist_orig"] = None
        action.revert()
        mock_del.assert_called_once()
        mock_write.assert_not_called()


# ============================================================================
# FirewallAction
# ============================================================================

class TestFirewallActionAttributes:

    def test_name(self):
        assert FirewallAction().name == "FirewallAction"


class TestFirewallActionSupportedOn:

    def test_supported_win10(self, win10_build):
        assert FirewallAction.supported_on(win10_build) is True

    def test_supported_win11(self, win11_build):
        assert FirewallAction.supported_on(win11_build) is True


class TestFirewallActionCheck:

    @patch(f"{_FW}.run_command_with_output",
           return_value=(0, "State                                OFF\nState                                OFF\nState                                OFF", ""))
    def test_check_true_when_all_off(self, mock_cmd):
        assert FirewallAction().check() is True

    @patch(f"{_FW}.run_command_with_output",
           return_value=(0, "State                                ON\nState                                OFF\nState                                OFF", ""))
    def test_check_false_when_one_on(self, mock_cmd):
        assert FirewallAction().check() is False

    @patch(f"{_FW}.run_command_with_output",
           return_value=(0, "State                                ON\nState                                ON\nState                                ON", ""))
    def test_check_false_when_all_on(self, mock_cmd):
        assert FirewallAction().check() is False

    @patch(f"{_FW}.run_command_with_output", return_value=(1, "", "error"))
    def test_check_false_on_command_failure(self, mock_cmd):
        assert FirewallAction().check() is False

    @patch(f"{_FW}.run_command_with_output", return_value=(0, "No profiles found", ""))
    def test_check_false_when_no_state_lines(self, mock_cmd):
        assert FirewallAction().check() is False


class TestFirewallActionApply:

    @patch(f"{_FW}.run_command", return_value=0)
    @patch(f"{_FW}.run_command_with_output",
           return_value=(0, "State                                ON", ""))
    def test_apply_calls_netsh_off(self, mock_query, mock_cmd):
        FirewallAction().apply()
        mock_cmd.assert_called_once()
        assert "state off" in mock_cmd.call_args[0][0]

    @patch(f"{_FW}.run_command", return_value=1)
    @patch(f"{_FW}.run_command_with_output",
           return_value=(0, "State                                ON", ""))
    def test_apply_raises_on_netsh_failure(self, mock_query, mock_cmd):
        with pytest.raises(OsConfigActionError):
            FirewallAction().apply()

    @patch(f"{_FW}.run_command", return_value=0)
    @patch(f"{_FW}.run_command_with_output",
           return_value=(0, "State                                OFF\nState                                OFF\nState                                OFF", ""))
    def test_apply_skips_when_already_off(self, mock_query, mock_cmd):
        FirewallAction().apply()
        mock_cmd.assert_not_called()


class TestFirewallActionRevert:

    @patch(f"{_FW}.run_command", return_value=0)
    def test_revert_calls_netsh_on(self, mock_cmd):
        FirewallAction().revert()
        mock_cmd.assert_called_once()
        assert "state on" in mock_cmd.call_args[0][0]

    @patch(f"{_FW}.run_command", return_value=1)
    def test_revert_logs_warning_on_failure(self, mock_cmd):
        """Non-zero return from netsh should not raise."""
        FirewallAction().revert()   # no exception


# ============================================================================
# UacAction
# ============================================================================

class TestUacActionAttributes:

    def test_name(self):
        assert UacAction().name == "UacAction"


class TestUacActionSupportedOn:

    def test_supported_win10(self, win10_build):
        assert UacAction.supported_on(win10_build) is True

    def test_supported_win11(self, win11_build):
        assert UacAction.supported_on(win11_build) is True


class TestUacActionCheck:

    @patch(f"{_UAC}.read_value_safe", return_value=0)
    def test_check_true_when_zero(self, mock_reg):
        assert UacAction().check() is True

    @patch(f"{_UAC}.read_value_safe", return_value=1)
    def test_check_false_when_one(self, mock_reg):
        assert UacAction().check() is False

    @patch(f"{_UAC}.read_value_safe", return_value=None)
    def test_check_false_when_absent(self, mock_reg):
        assert UacAction().check() is False


class TestUacActionApply:

    @patch(f"{_UAC}.write_value")
    @patch(f"{_UAC}.read_value_safe", return_value=1)   # UAC enabled
    def test_apply_writes_zero(self, mock_reg, mock_write):
        UacAction().apply()
        mock_write.assert_called_once()
        assert mock_write.call_args[0][3] == 0

    @patch(f"{_UAC}.write_value")
    @patch(f"{_UAC}.read_value_safe", return_value=0)   # already disabled
    def test_apply_skips_when_disabled(self, mock_reg, mock_write):
        UacAction().apply()
        mock_write.assert_not_called()

    @patch(f"{_UAC}.write_value")
    @patch(f"{_UAC}.read_value_safe", return_value=1)
    def test_apply_saves_snapshot(self, mock_reg, mock_write):
        action = UacAction()
        action.apply()
        assert action._snapshot.get("uac_enable_lua_orig") == 1


class TestUacActionRevert:

    @patch(f"{_UAC}.write_value")
    def test_revert_restores_original_value(self, mock_write):
        action = UacAction()
        action._snapshot["uac_enable_lua_orig"] = 1
        action.revert()
        mock_write.assert_called_once()
        assert mock_write.call_args[0][3] == 1

    @patch(f"{_UAC}.write_value")
    def test_revert_defaults_to_one_when_no_snapshot(self, mock_write):
        """If no snapshot (absent before apply), revert to safe default 1."""
        action = UacAction()
        # snapshot is empty
        action.revert()
        mock_write.assert_called_once()
        assert mock_write.call_args[0][3] == 1


# ============================================================================
# Cross-action: shared snapshot_store
# ============================================================================

class TestSharedSnapshotStore:

    @patch(f"{_OD}.write_value")
    @patch(f"{_OD}.read_value_safe", return_value=None)
    def test_onedrive_uses_shared_store(self, mock_reg, mock_write):
        store = {}
        action = OneDriveAction(snapshot_store=store)
        action.apply()
        assert "od_metered_orig" in store

    @patch(f"{_UAC}.write_value")
    @patch(f"{_UAC}.read_value_safe", return_value=1)
    def test_uac_and_onedrive_share_store(self, mock_reg, mock_write):
        store = {}
        with patch(f"{_OD}.write_value"), \
             patch(f"{_OD}.read_value_safe", return_value=None):
            OneDriveAction(snapshot_store=store).apply()
        UacAction(snapshot_store=store).apply()
        assert "od_metered_orig" in store
        assert "uac_enable_lua_orig" in store
