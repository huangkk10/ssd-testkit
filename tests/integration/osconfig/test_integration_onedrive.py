"""
Integration tests — OneDriveAction.

Verifies that OneDriveAction correctly applies and reverts three GPO
registry values that prevent OneDrive from syncing:

    HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\OneDrive
        DisableMeteredNetworkFileSync    = 1
        DisableFileSyncNGSC              = 1
        PreventNetworkTrafficPreUserSignIn = 1

Requirements:
  - Admin elevation (session-scoped autouse fixture in conftest.py)
  - Windows RS1 (Build >= 14393); tests are skipped on older builds.
"""

import winreg
import pytest

from lib.testtool.osconfig.actions.onedrive import OneDriveAction

pytestmark = [pytest.mark.integration, pytest.mark.admin]

_OD_KEY    = r"SOFTWARE\Policies\Microsoft\Windows\OneDrive"
_VAL_NAMES = (
    "DisableMeteredNetworkFileSync",
    "DisableFileSyncNGSC",
    "PreventNetworkTrafficPreUserSignIn",
)


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _read_od_values() -> dict:
    """Read current DWORD values from the OneDrive GPO key.

    Returns a dict of {val_name: int_or_None}.  None means the value
    (or the key itself) does not exist.
    """
    result = {}
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, _OD_KEY, access=winreg.KEY_READ
        ) as hk:
            for name in _VAL_NAMES:
                try:
                    data, _ = winreg.QueryValueEx(hk, name)
                    result[name] = data
                except FileNotFoundError:
                    result[name] = None
    except FileNotFoundError:
        result = {name: None for name in _VAL_NAMES}
    return result


def _all_set_to_1() -> bool:
    vals = _read_od_values()
    return all(v == 1 for v in vals.values())


# ------------------------------------------------------------------ #
# Tests                                                               #
# ------------------------------------------------------------------ #

class TestOneDriveActionApplyRevert:

    def test_apply_sets_all_three_values(self, build_info):
        if not OneDriveAction.supported_on(build_info):
            pytest.skip("OneDriveAction not supported on this OS build")

        action = OneDriveAction()
        try:
            action.apply()
            assert _all_set_to_1(), (
                f"Expected all three OneDrive GPO values == 1 after apply, "
                f"got: {_read_od_values()}"
            )
        finally:
            action.revert()

    def test_check_returns_true_after_apply(self, build_info):
        if not OneDriveAction.supported_on(build_info):
            pytest.skip("OneDriveAction not supported on this OS build")

        action = OneDriveAction()
        try:
            action.apply()
            assert action.check() is True
        finally:
            action.revert()

    def test_revert_removes_values_when_previously_absent(self, build_info):
        """When keys did not exist before apply, revert should delete them."""
        if not OneDriveAction.supported_on(build_info):
            pytest.skip("OneDriveAction not supported on this OS build")

        # Ensure the values are absent before starting
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, _OD_KEY,
                access=winreg.KEY_READ | winreg.KEY_WRITE,
            ) as hk:
                for name in _VAL_NAMES:
                    try:
                        winreg.DeleteValue(hk, name)
                    except FileNotFoundError:
                        pass
        except FileNotFoundError:
            pass  # key itself absent — that is fine

        action = OneDriveAction()
        action.apply()
        action.revert()

        vals = _read_od_values()
        assert all(v is None for v in vals.values()), (
            f"Expected all three values to be absent after revert, "
            f"got: {vals}"
        )

    def test_check_returns_false_after_revert(self, build_info):
        if not OneDriveAction.supported_on(build_info):
            pytest.skip("OneDriveAction not supported on this OS build")

        action = OneDriveAction()
        action.apply()
        action.revert()
        assert action.check() is False

    def test_apply_is_idempotent(self, build_info):
        """Calling apply() twice must not raise and check() stays True."""
        if not OneDriveAction.supported_on(build_info):
            pytest.skip("OneDriveAction not supported on this OS build")

        action = OneDriveAction()
        try:
            action.apply()
            action.apply()  # second call — should be a no-op
            assert action.check() is True
        finally:
            action.revert()


class TestDisableFileSyncNGSC:
    """
    Focused tests for the DisableFileSyncNGSC registry value only.

    OneDriveAction sets all three GPO values at once; these tests isolate
    the FileSyncNGSC behaviour by reading/asserting only that single value.
    """

    def _read_filesync_value(self) -> int | None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, _OD_KEY, access=winreg.KEY_READ
            ) as hk:
                data, _ = winreg.QueryValueEx(hk, "DisableFileSyncNGSC")
                return data
        except FileNotFoundError:
            return None

    def test_apply_sets_disable_file_sync_ngsc_to_1(self, build_info):
        """After apply(), DisableFileSyncNGSC must be 1."""
        if not OneDriveAction.supported_on(build_info):
            pytest.skip("OneDriveAction not supported on this OS build")

        action = OneDriveAction()
        try:
            action.apply()
            val = self._read_filesync_value()
            assert val == 1, (
                f"Expected DisableFileSyncNGSC == 1 after apply, got: {val!r}"
            )
        finally:
            action.revert()

    def test_revert_clears_disable_file_sync_ngsc(self, build_info):
        """After revert(), DisableFileSyncNGSC must be absent (None)."""
        if not OneDriveAction.supported_on(build_info):
            pytest.skip("OneDriveAction not supported on this OS build")

        # Ensure the value is absent before starting
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, _OD_KEY,
                access=winreg.KEY_READ | winreg.KEY_WRITE,
            ) as hk:
                try:
                    winreg.DeleteValue(hk, "DisableFileSyncNGSC")
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            pass

        action = OneDriveAction()
        action.apply()
        action.revert()

        val = self._read_filesync_value()
        assert val is None, (
            f"Expected DisableFileSyncNGSC to be absent after revert, got: {val!r}"
        )


class TestOneDriveActionUnsupported:

    def test_supported_on_returns_bool(self, build_info):
        result = OneDriveAction.supported_on(build_info)
        assert isinstance(result, bool)
