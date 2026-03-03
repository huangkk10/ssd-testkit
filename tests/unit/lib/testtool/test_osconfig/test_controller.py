"""
Unit tests for OsConfigStateManager and OsConfigController.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from lib.testtool.osconfig.config import OsConfigProfile
from lib.testtool.osconfig.state_manager import OsConfigStateManager
from lib.testtool.osconfig.controller import OsConfigController, _build_action_list
from lib.testtool.osconfig.exceptions import (
    OsConfigStateError,
    OsConfigNotSupportedError,
    OsConfigActionError,
)
from lib.testtool.osconfig.os_compat import WindowsBuildInfo

_CTL = "lib.testtool.osconfig.controller"


# ============================================================================
# Helpers
# ============================================================================

def _make_build(edition: str = "Pro", build: int = 19045) -> WindowsBuildInfo:
    return WindowsBuildInfo(
        major=10, build=build, edition=edition,
        version_tag="win10", product_name=f"Windows 10 {edition}",
    )


def _mock_action(name: str, supported: bool = True, check_val: bool = False):
    """Return a MagicMock resembling an AbstractOsAction."""
    a = MagicMock()
    a.name = name
    a.supported_on = MagicMock(return_value=supported)
    a.check = MagicMock(return_value=check_val)
    a.apply = MagicMock()
    a.revert = MagicMock()
    return a


# ============================================================================
# OsConfigStateManager
# ============================================================================

class TestOsConfigStateManagerSave:

    def test_save_creates_json_file(self, tmp_path):
        path = tmp_path / "snap.json"
        mgr = OsConfigStateManager(path=path)
        mgr.save({"key": 1})
        assert path.exists()
        data = json.loads(path.read_text())
        assert data == {"key": 1}

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "snap.json"
        mgr = OsConfigStateManager(path=path)
        mgr.save({"a": "b"})
        assert path.exists()

    def test_save_raises_on_write_error(self, tmp_path):
        path = tmp_path / "snap.json"
        mgr = OsConfigStateManager(path=path)
        with patch.object(Path, "open", side_effect=OSError("permission denied")):
            with pytest.raises(OsConfigStateError, match="Cannot write snapshot"):
                mgr.save({})


class TestOsConfigStateManagerLoad:

    def test_load_returns_dict(self, tmp_path):
        path = tmp_path / "snap.json"
        path.write_text(json.dumps({"x": 42}))
        mgr = OsConfigStateManager(path=path)
        result = mgr.load()
        assert result == {"x": 42}

    def test_load_raises_when_missing(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        mgr = OsConfigStateManager(path=path)
        with pytest.raises(OsConfigStateError, match="not found"):
            mgr.load()

    def test_load_raises_on_invalid_json(self, tmp_path):
        path = tmp_path / "snap.json"
        path.write_text("not json }{")
        mgr = OsConfigStateManager(path=path)
        with pytest.raises(OsConfigStateError, match="Cannot read snapshot"):
            mgr.load()

    def test_roundtrip(self, tmp_path):
        path = tmp_path / "snap.json"
        mgr = OsConfigStateManager(path=path)
        data = {"auto_reboot_orig": 1, "fast_startup_orig": 1, "multi": [1, 2]}
        mgr.save(data)
        assert mgr.load() == data


class TestOsConfigStateManagerExists:

    def test_exists_true_when_file_present(self, tmp_path):
        path = tmp_path / "snap.json"
        path.write_text("{}")
        assert OsConfigStateManager(path=path).exists() is True

    def test_exists_false_when_absent(self, tmp_path):
        path = tmp_path / "nofile.json"
        assert OsConfigStateManager(path=path).exists() is False


class TestOsConfigStateManagerDelete:

    def test_delete_removes_file(self, tmp_path):
        path = tmp_path / "snap.json"
        path.write_text("{}")
        mgr = OsConfigStateManager(path=path)
        mgr.delete()
        assert not path.exists()

    def test_delete_idempotent_when_absent(self, tmp_path):
        path = tmp_path / "nofile.json"
        OsConfigStateManager(path=path).delete()   # must not raise

    def test_delete_raises_on_os_error(self, tmp_path):
        path = tmp_path / "snap.json"
        path.write_text("{}")
        mgr = OsConfigStateManager(path=path)
        with patch.object(Path, "unlink", side_effect=OSError("locked")):
            with pytest.raises(OsConfigStateError, match="Cannot delete"):
                mgr.delete()


# ============================================================================
# _build_action_list
# ============================================================================

class TestBuildActionList:

    def test_empty_profile_yields_no_actions(self):
        actions = _build_action_list(OsConfigProfile(), {})
        assert actions == []

    def test_each_bool_flag_adds_one_action(self):
        p = OsConfigProfile(
            disable_search_index=True,
            disable_sysmain=True,
            disable_windows_update=True,
        )
        actions = _build_action_list(p, {})
        assert len(actions) == 3

    def test_power_plan_string_adds_action(self):
        p = OsConfigProfile(power_plan="balanced")
        actions = _build_action_list(p, {})
        assert len(actions) == 1
        assert actions[0].name == "PowerPlanAction"

    def test_empty_power_plan_adds_no_action(self):
        p = OsConfigProfile(power_plan="")
        actions = _build_action_list(p, {})
        assert actions == []

    def test_manage_pagefile_uses_drive_params(self):
        p = OsConfigProfile(manage_pagefile=True, pagefile_drive="D:",
                            pagefile_min_mb=2048, pagefile_max_mb=4096)
        actions = _build_action_list(p, {})
        assert len(actions) == 1
        pf = actions[0]
        assert pf._drive == "D:"
        assert pf._min_mb == 2048
        assert pf._max_mb == 4096

    def test_actions_share_snapshot_store(self):
        snap = {}
        p = OsConfigProfile(disable_search_index=True, disable_sysmain=True)
        actions = _build_action_list(p, snap)
        for a in actions:
            assert a._snapshot is snap

    def test_full_default_profile_builds_32_actions(self):
        actions = _build_action_list(OsConfigProfile.default(), {})
        assert len(actions) == 32

    def test_timeout_types_get_correct_names(self):
        p = OsConfigProfile(
            disable_monitor_timeout=True,
            disable_standby_timeout=True,
            disable_hibernate_timeout=True,
            disable_disk_timeout=True,
        )
        actions = _build_action_list(p, {})
        names = [a.name for a in actions]
        assert "PowerTimeoutAction[monitor]" in names
        assert "PowerTimeoutAction[standby]" in names
        assert "PowerTimeoutAction[hibernate]" in names
        assert "PowerTimeoutAction[disk]" in names


# ============================================================================
# OsConfigController — Construction
# ============================================================================

class TestOsConfigControllerConstruction:

    def test_default_profile_when_none_given(self, win10_build):
        ctrl = OsConfigController(build_info=win10_build)
        assert isinstance(ctrl.profile, OsConfigProfile)

    def test_actions_property(self, win10_build):
        p = OsConfigProfile(disable_search_index=True)
        ctrl = OsConfigController(profile=p, build_info=win10_build)
        assert len(ctrl.actions) == 1

    def test_actions_returns_copy(self, win10_build):
        p = OsConfigProfile(disable_search_index=True)
        ctrl = OsConfigController(profile=p, build_info=win10_build)
        lst = ctrl.actions
        lst.clear()
        assert len(ctrl.actions) == 1   # original unchanged

    def test_snapshot_initially_empty(self, win10_build):
        ctrl = OsConfigController(build_info=win10_build)
        assert ctrl.snapshot == {}


# ============================================================================
# OsConfigController — apply_all
# ============================================================================

class TestOsConfigControllerApplyAll:

    def _ctrl_with_mocks(self, actions, profile=None, build_info=None,
                         state_manager=None):
        """Build a controller and replace its action list with mocks."""
        ctrl = OsConfigController(
            profile=profile or OsConfigProfile(),
            build_info=build_info or _make_build(),
            state_manager=state_manager,
        )
        ctrl._actions = actions
        return ctrl

    def test_apply_calls_apply_on_each_action(self):
        a1 = _mock_action("A1")
        a2 = _mock_action("A2")
        ctrl = self._ctrl_with_mocks([a1, a2])
        ctrl.apply_all()
        a1.apply.assert_called_once()
        a2.apply.assert_called_once()

    def test_apply_returns_applied_status(self):
        a1 = _mock_action("A1")
        ctrl = self._ctrl_with_mocks([a1])
        result = ctrl.apply_all()
        assert result["A1"] == "applied"

    def test_apply_skips_unsupported_action(self):
        a1 = _mock_action("A1", supported=False)
        ctrl = self._ctrl_with_mocks([a1])
        result = ctrl.apply_all()
        a1.apply.assert_not_called()
        assert result["A1"] == "unsupported"

    def test_apply_raises_on_unsupported_when_fail_on_unsupported(self):
        a1 = _mock_action("A1", supported=False)
        p = OsConfigProfile(fail_on_unsupported=True)
        ctrl = self._ctrl_with_mocks([a1], profile=p)
        with pytest.raises(OsConfigNotSupportedError):
            ctrl.apply_all()

    def test_apply_records_error_on_action_error(self):
        a1 = _mock_action("A1")
        a1.apply.side_effect = OsConfigActionError("boom")
        ctrl = self._ctrl_with_mocks([a1])
        result = ctrl.apply_all()
        assert result["A1"].startswith("error:")

    def test_apply_continues_after_action_error(self):
        a1 = _mock_action("A1")
        a1.apply.side_effect = OsConfigActionError("boom")
        a2 = _mock_action("A2")
        ctrl = self._ctrl_with_mocks([a1, a2])
        result = ctrl.apply_all()
        a2.apply.assert_called_once()
        assert result["A2"] == "applied"

    def test_apply_saves_snapshot_via_state_manager(self, tmp_path):
        sm = OsConfigStateManager(path=tmp_path / "snap.json")
        a1 = _mock_action("A1")
        ctrl = self._ctrl_with_mocks([a1], state_manager=sm)
        ctrl.apply_all()
        assert sm.exists()


# ============================================================================
# OsConfigController — revert_all
# ============================================================================

class TestOsConfigControllerRevertAll:

    def _ctrl_with_mocks(self, actions, state_manager=None):
        ctrl = OsConfigController(
            build_info=_make_build(),
            state_manager=state_manager,
        )
        ctrl._actions = actions
        return ctrl

    def test_revert_calls_revert_on_each_action(self):
        a1 = _mock_action("A1")
        a2 = _mock_action("A2")
        ctrl = self._ctrl_with_mocks([a1, a2])
        ctrl.revert_all()
        a1.revert.assert_called_once()
        a2.revert.assert_called_once()

    def test_revert_order_is_reversed(self):
        call_order = []
        a1 = _mock_action("A1")
        a2 = _mock_action("A2")
        a3 = _mock_action("A3")
        a1.revert.side_effect = lambda: call_order.append("A1")
        a2.revert.side_effect = lambda: call_order.append("A2")
        a3.revert.side_effect = lambda: call_order.append("A3")
        ctrl = self._ctrl_with_mocks([a1, a2, a3])
        ctrl.revert_all()
        assert call_order == ["A3", "A2", "A1"]

    def test_revert_returns_reverted_status(self):
        a1 = _mock_action("A1")
        ctrl = self._ctrl_with_mocks([a1])
        result = ctrl.revert_all()
        assert result["A1"] == "reverted"

    def test_revert_skips_unsupported(self):
        a1 = _mock_action("A1", supported=False)
        ctrl = self._ctrl_with_mocks([a1])
        result = ctrl.revert_all()
        a1.revert.assert_not_called()
        assert result["A1"] == "unsupported"

    def test_revert_records_error_on_action_error(self):
        a1 = _mock_action("A1")
        a1.revert.side_effect = OsConfigActionError("fail")
        ctrl = self._ctrl_with_mocks([a1])
        result = ctrl.revert_all()
        assert result["A1"].startswith("error:")

    def test_revert_loads_snapshot_from_state_manager(self, tmp_path):
        path = tmp_path / "snap.json"
        path.write_text(json.dumps({"saved_key": 99}))
        sm = OsConfigStateManager(path=path)
        ctrl = self._ctrl_with_mocks([], state_manager=sm)
        ctrl.revert_all()
        assert ctrl.snapshot.get("saved_key") == 99

    def test_revert_deletes_snapshot_file(self, tmp_path):
        path = tmp_path / "snap.json"
        path.write_text("{}")
        sm = OsConfigStateManager(path=path)
        ctrl = self._ctrl_with_mocks([], state_manager=sm)
        ctrl.revert_all()
        assert not path.exists()


# ============================================================================
# OsConfigController — check_all
# ============================================================================

class TestOsConfigControllerCheckAll:

    def _ctrl_with_mocks(self, actions):
        ctrl = OsConfigController(build_info=_make_build())
        ctrl._actions = actions
        return ctrl

    def test_check_all_returns_bool_per_action(self):
        a1 = _mock_action("A1", check_val=True)
        a2 = _mock_action("A2", check_val=False)
        ctrl = self._ctrl_with_mocks([a1, a2])
        result = ctrl.check_all()
        assert result == {"A1": True, "A2": False}

    def test_check_all_unsupported_maps_to_none(self):
        a1 = _mock_action("A1", supported=False)
        ctrl = self._ctrl_with_mocks([a1])
        result = ctrl.check_all()
        assert result["A1"] is None
        a1.check.assert_not_called()

    def test_check_all_exception_maps_to_none(self):
        a1 = _mock_action("A1")
        a1.check.side_effect = RuntimeError("unexpected")
        ctrl = self._ctrl_with_mocks([a1])
        result = ctrl.check_all()
        assert result["A1"] is None

    def test_check_all_empty_actions_returns_empty_dict(self):
        ctrl = self._ctrl_with_mocks([])
        assert ctrl.check_all() == {}


# ============================================================================
# Integration: top-level imports
# ============================================================================

class TestTopLevelImports:

    def test_import_profile_from_package(self):
        from lib.testtool.osconfig import OsConfigProfile
        assert OsConfigProfile is not None

    def test_import_state_manager_from_package(self):
        from lib.testtool.osconfig import OsConfigStateManager
        assert OsConfigStateManager is not None

    def test_import_controller_from_package(self):
        from lib.testtool.osconfig import OsConfigController
        assert OsConfigController is not None
