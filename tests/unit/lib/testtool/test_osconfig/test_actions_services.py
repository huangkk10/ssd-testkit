"""
Unit tests for Phase 2 service actions.

All subprocess and registry calls are fully mocked.
Tests cover: check(), apply(), revert(), supported_on() for each action class.
"""

import pytest
from unittest.mock import patch, call, MagicMock

from lib.testtool.osconfig.actions.search_index import SearchIndexAction
from lib.testtool.osconfig.actions.sysmain import SysMainAction
from lib.testtool.osconfig.actions.windows_update import WindowsUpdateAction
from lib.testtool.osconfig.actions.wer import WerAction
from lib.testtool.osconfig.actions.telemetry import TelemetryAction
from lib.testtool.osconfig.actions.pcasvc import PcaSvcAction
from lib.testtool.osconfig.exceptions import OsConfigActionError

# Patch targets
_BASE = "lib.testtool.osconfig.actions._base_service_action"
_WU   = "lib.testtool.osconfig.actions.windows_update"
_TEL  = "lib.testtool.osconfig.actions.telemetry"
_REG  = "lib.testtool.osconfig.registry_helper"


# ---------------------------------------------------------------------------
# Parametrised: instantiation + class attributes
# ---------------------------------------------------------------------------

_SIMPLE_ACTIONS = [
    (SearchIndexAction, "WSearch",   "search_index"),
    (SysMainAction,     "SysMain",   "sysmain"),
    (WerAction,         "WerSvc",    "wer"),
    (PcaSvcAction,      "PcaSvc",    "pcasvc"),
]


class TestServiceActionAttributes:

    @pytest.mark.parametrize("cls, svc, cap", _SIMPLE_ACTIONS)
    def test_service_name(self, cls, svc, cap):
        action = cls()
        assert action.service_name == svc

    @pytest.mark.parametrize("cls, svc, cap", _SIMPLE_ACTIONS)
    def test_capability_key(self, cls, svc, cap):
        action = cls()
        assert action.capability_key == cap

    @pytest.mark.parametrize("cls, svc, cap", _SIMPLE_ACTIONS)
    def test_name_attribute_set(self, cls, svc, cap):
        action = cls()
        assert action.name and action.name != "BaseServiceAction"


# ---------------------------------------------------------------------------
# check() - reads registry Start value
# ---------------------------------------------------------------------------

class TestServiceActionCheck:

    @pytest.mark.parametrize("cls", [
        SearchIndexAction, SysMainAction, WerAction, PcaSvcAction,
        WindowsUpdateAction, TelemetryAction,
    ])
    @patch(f"{_BASE}.read_value_safe", return_value=4)  # 4 = Disabled
    def test_check_true_when_disabled(self, mock_reg, cls):
        assert cls().check() is True

    @pytest.mark.parametrize("cls", [
        SearchIndexAction, SysMainAction, WerAction, PcaSvcAction,
        WindowsUpdateAction, TelemetryAction,
    ])
    @patch(f"{_BASE}.read_value_safe", return_value=2)  # 2 = Auto
    def test_check_false_when_auto(self, mock_reg, cls):
        assert cls().check() is False

    @pytest.mark.parametrize("cls", [
        SearchIndexAction, SysMainAction, WerAction, PcaSvcAction,
        WindowsUpdateAction, TelemetryAction,
    ])
    @patch(f"{_BASE}.read_value_safe", return_value=3)  # 3 = Manual
    def test_check_false_when_manual(self, mock_reg, cls):
        assert cls().check() is False

    @pytest.mark.parametrize("cls", [
        SearchIndexAction, SysMainAction, WerAction, PcaSvcAction,
        WindowsUpdateAction, TelemetryAction,
    ])
    @patch(f"{_BASE}.read_value_safe", return_value=None)  # service not found
    def test_check_true_when_service_missing(self, mock_reg, cls):
        """A missing service is treated as already disabled."""
        assert cls().check() is True


# ---------------------------------------------------------------------------
# apply() — happy path
# ---------------------------------------------------------------------------

class TestServiceActionApply:

    @patch(f"{_BASE}.run_command", return_value=0)
    @patch(f"{_BASE}.run_command_with_output", return_value=(0, "STATE : 4  STOPPED", ""))
    @patch(f"{_BASE}.read_value_safe", return_value=2)  # Auto → not yet disabled
    def test_apply_calls_sc_stop_and_config(self, mock_reg, mock_query, mock_cmd):
        action = SearchIndexAction()
        action.apply()
        calls = [str(c) for c in mock_cmd.call_args_list]
        assert any("sc stop WSearch" in c for c in calls)
        assert any("sc config WSearch start=disabled" in c for c in calls)

    @patch(f"{_BASE}.run_command", return_value=0)
    @patch(f"{_BASE}.run_command_with_output", return_value=(0, "STATE : 4  STOPPED", ""))
    @patch(f"{_BASE}.read_value_safe", return_value=2)
    def test_apply_saves_snapshot(self, mock_reg, mock_query, mock_cmd):
        action = SearchIndexAction()
        action.apply()
        assert action._snapshot.get("start_type") == 2
        assert "was_running" in action._snapshot

    @patch(f"{_BASE}.run_command", return_value=0)
    @patch(f"{_BASE}.run_command_with_output", return_value=(0, "STATE : 4  RUNNING", ""))
    @patch(f"{_BASE}.read_value_safe", return_value=2)
    def test_apply_records_was_running(self, mock_reg, mock_query, mock_cmd):
        action = SearchIndexAction()
        action.apply()
        assert action._snapshot.get("was_running") is True

    @patch(f"{_BASE}.run_command")
    @patch(f"{_BASE}.run_command_with_output", return_value=(0, "STOPPED", ""))
    @patch(f"{_BASE}.read_value_safe", return_value=4)  # already disabled
    def test_apply_skips_when_already_disabled(self, mock_reg, mock_query, mock_cmd):
        action = SearchIndexAction()
        action.apply()
        mock_cmd.assert_not_called()

    @patch(f"{_BASE}.run_command", side_effect=[0, 5])   # stop ok, config fails
    @patch(f"{_BASE}.run_command_with_output", return_value=(0, "STOPPED", ""))
    @patch(f"{_BASE}.read_value_safe", return_value=2)
    def test_apply_raises_on_sc_config_failure(self, mock_reg, mock_query, mock_cmd):
        with pytest.raises(OsConfigActionError, match="start=disabled"):
            SearchIndexAction().apply()


# ---------------------------------------------------------------------------
# revert()
# ---------------------------------------------------------------------------

class TestServiceActionRevert:

    @patch(f"{_BASE}.run_command", return_value=0)
    def test_revert_restores_start_type(self, mock_cmd):
        action = SearchIndexAction()
        action._save_snapshot("start_type", 2)   # was Auto
        action._save_snapshot("was_running", False)
        action.revert()
        sc_calls = [c[0][0] for c in mock_cmd.call_args_list]
        assert any("start=auto" in c for c in sc_calls)
        assert not any("sc start" in c for c in sc_calls)

    @patch(f"{_BASE}.run_command", return_value=0)
    def test_revert_starts_service_if_was_running(self, mock_cmd):
        action = SearchIndexAction()
        action._save_snapshot("start_type", 2)
        action._save_snapshot("was_running", True)
        action.revert()
        sc_calls = [c[0][0] for c in mock_cmd.call_args_list]
        assert any("sc start WSearch" in c for c in sc_calls)

    @patch(f"{_BASE}.run_command")
    def test_revert_noop_when_no_snapshot(self, mock_cmd):
        action = SearchIndexAction()
        action.revert()   # no snapshot set
        mock_cmd.assert_not_called()

    @patch(f"{_BASE}.run_command", return_value=0)
    def test_revert_manual_start_type(self, mock_cmd):
        action = SysMainAction()
        action._save_snapshot("start_type", 3)   # was Manual
        action._save_snapshot("was_running", False)
        action.revert()
        sc_calls = [c[0][0] for c in mock_cmd.call_args_list]
        assert any("start=demand" in c for c in sc_calls)


# ---------------------------------------------------------------------------
# supported_on() — capability matrix
# ---------------------------------------------------------------------------

class TestServiceActionSupportedOn:

    def test_search_index_not_supported_on_server(self, win_server_build):
        assert SearchIndexAction.supported_on(win_server_build) is False

    def test_search_index_supported_on_win10(self, win10_build):
        assert SearchIndexAction.supported_on(win10_build) is True

    def test_sysmain_supported_everywhere(self, win10_build, win11_build):
        assert SysMainAction.supported_on(win10_build) is True
        assert SysMainAction.supported_on(win11_build) is True

    def test_wer_supported_everywhere(self, win10_build):
        assert WerAction.supported_on(win10_build) is True

    def test_pcasvc_supported_everywhere(self, win10_build):
        assert PcaSvcAction.supported_on(win10_build) is True


# ---------------------------------------------------------------------------
# WindowsUpdateAction — GPO extra registry write
# ---------------------------------------------------------------------------

class TestWindowsUpdateAction:

    @patch(f"{_BASE}.run_command", return_value=0)
    @patch(f"{_BASE}.run_command_with_output", return_value=(0, "STOPPED", ""))
    @patch(f"{_BASE}.read_value_safe", return_value=2)
    @patch(f"{_WU}.read_value_safe", return_value=None)
    @patch(f"{_WU}.write_value")
    def test_apply_writes_gpo_key(self, mock_write, mock_gpo_snap,
                                   mock_reg, mock_query, mock_cmd):
        action = WindowsUpdateAction()
        action.apply()
        # Verify NoAutoUpdate was written
        mock_write.assert_called()
        write_args = [c[0] for c in mock_write.call_args_list]
        assert any("NoAutoUpdate" in str(a) for a in write_args)

    @patch(f"{_BASE}.run_command", return_value=0)
    @patch(f"{_WU}.write_value")
    @patch(f"{_WU}.delete_value")
    def test_revert_deletes_gpo_when_was_absent(self, mock_del, mock_write, mock_cmd):
        action = WindowsUpdateAction()
        action._save_snapshot("start_type", 2)
        action._save_snapshot("was_running", False)
        action._save_snapshot("no_auto_update_gpo", None)  # was absent
        action.revert()
        mock_del.assert_called_once()

    @patch(f"{_BASE}.run_command", return_value=0)
    @patch(f"{_WU}.write_value")
    @patch(f"{_WU}.delete_value")
    def test_revert_restores_gpo_when_was_set(self, mock_del, mock_write, mock_cmd):
        action = WindowsUpdateAction()
        action._save_snapshot("start_type", 2)
        action._save_snapshot("was_running", False)
        action._save_snapshot("no_auto_update_gpo", 0)   # was 0
        action.revert()
        mock_del.assert_not_called()
        mock_write.assert_called()


# ---------------------------------------------------------------------------
# TelemetryAction — telemetry policy extra registry write
# ---------------------------------------------------------------------------

class TestTelemetryAction:

    @patch(f"{_BASE}.run_command", return_value=0)
    @patch(f"{_BASE}.run_command_with_output", return_value=(0, "STOPPED", ""))
    @patch(f"{_BASE}.read_value_safe", return_value=2)
    @patch(f"{_TEL}.read_value_safe", return_value=None)
    @patch(f"{_TEL}.write_value")
    def test_apply_writes_allow_telemetry(self, mock_write, mock_tel_snap,
                                           mock_reg, mock_query, mock_cmd):
        action = TelemetryAction()
        action.apply()
        write_args = [c[0] for c in mock_write.call_args_list]
        assert any("AllowTelemetry" in str(a) for a in write_args)

    @patch(f"{_BASE}.run_command", return_value=0)
    @patch(f"{_TEL}.write_value")
    @patch(f"{_TEL}.delete_value")
    def test_revert_deletes_telemetry_when_was_absent(self, mock_del, mock_write, mock_cmd):
        action = TelemetryAction()
        action._save_snapshot("start_type", 2)
        action._save_snapshot("was_running", False)
        action._save_snapshot("allow_telemetry_orig", None)
        action.revert()
        mock_del.assert_called_once()


# ---------------------------------------------------------------------------
# Shared snapshot store across multiple actions
# ---------------------------------------------------------------------------

class TestSharedSnapshotStore:

    @patch(f"{_BASE}.run_command", return_value=0)
    @patch(f"{_BASE}.run_command_with_output", return_value=(0, "STOPPED", ""))
    @patch(f"{_BASE}.read_value_safe", return_value=2)
    def test_shared_snapshot_store_isolation(self, mock_reg, mock_query, mock_cmd):
        """Two actions sharing one store must not overwrite each other's keys."""
        store = {}
        a1 = SearchIndexAction(snapshot_store=store)
        a2 = SysMainAction(snapshot_store=store)
        # Both apply into the same store – keys should coexist
        # (In real usage the controller namespaces key names per action,
        #  but here we verify the store reference is shared)
        a1._save_snapshot("test_key", "from_a1")
        a2._save_snapshot("other_key", "from_a2")
        assert store["test_key"] == "from_a1"
        assert store["other_key"] == "from_a2"
