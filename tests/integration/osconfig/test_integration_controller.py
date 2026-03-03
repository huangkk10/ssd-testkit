"""
Integration tests — OsConfigController full cycle.

Uses a carefully chosen **safe minimal profile** that:
  - Only touches registry-based settings (no bcdedit/powercfg that need reboot)
  - Can be reliably reverted in the same process
  - Does not disable critical services needed for the test runner itself

Safe profile (immediate-revert, registry only):
    fast_startup, notifications, cortana, background_apps,
    auto_reboot, memory_dump,
    defrag_schedule, defender_scan_schedule,
    power_plan (high_performance)
"""

import pytest

from lib.testtool.osconfig.config import OsConfigProfile
from lib.testtool.osconfig.controller import OsConfigController

pytestmark = [pytest.mark.integration, pytest.mark.admin]

_SAFE_PROFILE = OsConfigProfile(
    # System (registry only)
    disable_fast_startup=True,
    disable_notifications=True,
    disable_cortana=True,
    disable_background_apps=True,
    # Boot crash control (registry only)
    disable_auto_reboot=True,
    set_small_memory_dump=True,
    # Schedule
    disable_defrag_schedule=True,
    disable_defender_scan_schedule=True,
    # Power plan (immediate, no reboot)
    power_plan="high_performance",
)


class TestOsConfigControllerApplyRevert:

    def test_apply_all_returns_applied_or_unsupported(self, build_info):
        ctrl = OsConfigController(profile=_SAFE_PROFILE, build_info=build_info)
        try:
            results = ctrl.apply_all()
        finally:
            ctrl.revert_all()

        for name, status in results.items():
            assert status in ("applied", "unsupported", "skipped") or \
                   status.startswith("error:"), (
                f"Unexpected status for {name!r}: {status!r}"
            )

    def test_revert_all_returns_reverted_or_unsupported(self, build_info):
        ctrl = OsConfigController(profile=_SAFE_PROFILE, build_info=build_info)
        ctrl.apply_all()
        results = ctrl.revert_all()

        for name, status in results.items():
            assert status in ("reverted", "unsupported") or \
                   status.startswith("error:"), (
                f"Unexpected revert status for {name!r}: {status!r}"
            )

    def test_check_all_after_apply(self, build_info):
        ctrl = OsConfigController(profile=_SAFE_PROFILE, build_info=build_info)
        try:
            ctrl.apply_all()
            status = ctrl.check_all()
        finally:
            ctrl.revert_all()

        # At least the registry-only safe actions should report True
        applied = [v for v in status.values() if v is True]
        assert len(applied) > 0, (
            "check_all() returned no True values after apply_all()"
        )

    def test_check_all_after_revert_has_fewer_true(self, build_info):
        ctrl = OsConfigController(profile=_SAFE_PROFILE, build_info=build_info)
        ctrl.apply_all()
        after_apply = sum(1 for v in ctrl.check_all().values() if v is True)

        ctrl.revert_all()
        after_revert = sum(1 for v in ctrl.check_all().values() if v is True)

        assert after_revert < after_apply or after_revert == 0, (
            f"Expected fewer True after revert: "
            f"apply={after_apply}, revert={after_revert}"
        )

    def test_no_error_statuses_in_safe_profile(self, build_info):
        ctrl = OsConfigController(profile=_SAFE_PROFILE, build_info=build_info)
        try:
            results = ctrl.apply_all()
        finally:
            ctrl.revert_all()

        errors = {k: v for k, v in results.items() if v.startswith("error:")}
        assert errors == {}, (
            f"Errors during apply_all with safe profile: {errors}"
        )


class TestOsConfigControllerStateManager:

    def test_snapshot_persisted_to_disk(self, build_info, tmp_path):
        from lib.testtool.osconfig.state_manager import OsConfigStateManager
        sm = OsConfigStateManager(path=tmp_path / "snap.json")
        ctrl = OsConfigController(
            profile=_SAFE_PROFILE,
            build_info=build_info,
            state_manager=sm,
        )
        try:
            ctrl.apply_all()
            assert sm.exists(), "Snapshot file should exist after apply_all()"
        finally:
            ctrl.revert_all()

        # revert_all() deletes the snapshot file
        assert not sm.exists(), "Snapshot file should be deleted after revert_all()"

    def test_snapshot_can_be_reloaded(self, build_info, tmp_path):
        """Simulate a reboot: apply in one controller, revert in a new one."""
        from lib.testtool.osconfig.state_manager import OsConfigStateManager
        snap_path = tmp_path / "snap.json"
        sm1 = OsConfigStateManager(path=snap_path)

        # Controller 1: apply
        ctrl1 = OsConfigController(
            profile=_SAFE_PROFILE, build_info=build_info, state_manager=sm1
        )
        ctrl1.apply_all()
        assert sm1.exists()

        # Controller 2: new instance, same snapshot path → revert
        sm2 = OsConfigStateManager(path=snap_path)
        ctrl2 = OsConfigController(
            profile=_SAFE_PROFILE, build_info=build_info, state_manager=sm2
        )
        results = ctrl2.revert_all()

        errors = {k: v for k, v in results.items() if v.startswith("error:")}
        assert errors == {}, f"Revert errors in new controller: {errors}"
        assert not snap_path.exists(), "Snapshot should be deleted after revert"


class TestOsConfigControllerEmptyProfile:

    def test_empty_profile_apply_is_noop(self, build_info):
        ctrl = OsConfigController(
            profile=OsConfigProfile(), build_info=build_info
        )
        results = ctrl.apply_all()
        assert results == {}

    def test_empty_profile_revert_is_noop(self, build_info):
        ctrl = OsConfigController(
            profile=OsConfigProfile(), build_info=build_info
        )
        results = ctrl.revert_all()
        assert results == {}
