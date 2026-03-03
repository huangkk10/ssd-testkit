"""
Integration tests — DefenderAction (Windows Defender Real-time Monitoring).

DefenderAction uses a two-tier approach:
  Tier 1 — PowerShell Set-MpPreference -DisableRealtimeMonitoring $true
  Tier 2 — Registry GPO fallback:
             HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender
                 DisableAntiSpyware = 1

⚠️  Tamper Protection (Build ≥ 18362) may block BOTH tiers.
    When Tamper Protection is active the PowerShell command is rejected and
    the registry write is silently ignored by the Defender service.
    These tests detect the TP state and skip / warn accordingly.

Requirements:
  - Admin elevation (session-scoped autouse fixture in conftest.py)
"""

import winreg
import subprocess
import pytest

from lib.testtool.osconfig.actions.defender import DefenderAction

pytestmark = [pytest.mark.integration, pytest.mark.admin]

_DEF_KEY     = r"SOFTWARE\Policies\Microsoft\Windows Defender"
_VAL_DISABLE = "DisableAntiSpyware"

# Tamper Protection registry path (read-only; written by the OS itself)
_TP_KEY      = r"SOFTWARE\Microsoft\Windows Defender\Features"
_TP_VAL      = "TamperProtection"
_TP_ENABLED  = 5   # value == 5 means Tamper Protection is ON


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _tamper_protection_enabled() -> bool:
    """Return True when Windows Defender Tamper Protection is active."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, _TP_KEY, access=winreg.KEY_READ
        ) as hk:
            data, _ = winreg.QueryValueEx(hk, _TP_VAL)
            return int(data) == _TP_ENABLED
    except (FileNotFoundError, OSError, ValueError):
        return False


def _read_disable_antispyware() -> int | None:
    """Read DisableAntiSpyware from the Defender GPO key; None if absent."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, _DEF_KEY, access=winreg.KEY_READ
        ) as hk:
            data, _ = winreg.QueryValueEx(hk, _VAL_DISABLE)
            return data
    except FileNotFoundError:
        return None


def _realtime_monitoring_enabled() -> bool | None:
    """
    Query Get-MpPreference to check real-time monitoring state.
    Returns True/False, or None if the command fails.
    """
    try:
        result = subprocess.run(
            [
                "powershell", "-NonInteractive", "-Command",
                "(Get-MpPreference).DisableRealtimeMonitoring",
            ],
            capture_output=True, text=True, timeout=15,
        )
        val = result.stdout.strip().lower()
        if val == "false":
            return True    # monitoring is ON  (DisableRealtime=False)
        if val == "true":
            return False   # monitoring is OFF (DisableRealtime=True)
        return None
    except Exception:
        return None


# ------------------------------------------------------------------ #
# Tests — Registry GPO layer                                          #
# ------------------------------------------------------------------ #

class TestDefenderRegistryPolicy:
    """
    Test the registry GPO value independently of PowerShell / Tamper Protection.

    Writing to HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender is
    possible even when Tamper Protection is on, but Defender may ignore
    the value at runtime.  These tests verify that the *write/delete*
    operations behave correctly.
    """

    def test_apply_writes_disable_antispyware(self, build_info):
        """After apply(), DisableAntiSpyware must be 1 in the GPO key."""
        if not DefenderAction.supported_on(build_info):
            pytest.skip("DefenderAction not supported on this OS build")

        action = DefenderAction()
        try:
            action.apply()
            val = _read_disable_antispyware()
            assert val == 1, (
                f"Expected DisableAntiSpyware == 1 after apply, got {val!r}"
            )
        finally:
            action.revert()

    def test_check_returns_true_after_apply(self, build_info):
        """check() monitors the registry GPO value → must be True after apply."""
        if not DefenderAction.supported_on(build_info):
            pytest.skip("DefenderAction not supported on this OS build")

        action = DefenderAction()
        try:
            action.apply()
            assert action.check() is True, "check() returned False after apply()"
        finally:
            action.revert()

    def test_revert_removes_disable_antispyware(self, build_info):
        """
        When DisableAntiSpyware was absent before apply,
        revert() must delete it (not leave it as 1).
        """
        if not DefenderAction.supported_on(build_info):
            pytest.skip("DefenderAction not supported on this OS build")

        # Ensure the value is absent before we start
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, _DEF_KEY,
                access=winreg.KEY_READ | winreg.KEY_WRITE,
            ) as hk:
                try:
                    winreg.DeleteValue(hk, _VAL_DISABLE)
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            pass  # key itself absent — fine

        action = DefenderAction()
        action.apply()
        action.revert()

        val = _read_disable_antispyware()
        assert val is None, (
            f"Expected DisableAntiSpyware absent after revert, got {val!r}"
        )

    def test_check_returns_false_after_revert(self, build_info):
        """check() must return False once revert() has cleaned up."""
        if not DefenderAction.supported_on(build_info):
            pytest.skip("DefenderAction not supported on this OS build")

        action = DefenderAction()
        action.apply()
        action.revert()
        assert action.check() is False, "check() still True after revert()"

    def test_apply_is_idempotent(self, build_info):
        """Calling apply() twice must not raise and check() stays True."""
        if not DefenderAction.supported_on(build_info):
            pytest.skip("DefenderAction not supported on this OS build")

        action = DefenderAction()
        try:
            action.apply()
            action.apply()   # second call — should be a no-op
            assert action.check() is True
        finally:
            action.revert()


# ------------------------------------------------------------------ #
# Tests — Tamper Protection awareness                                 #
# ------------------------------------------------------------------ #

class TestDefenderTamperProtection:
    """
    Tests that confirm behaviour under different Tamper Protection states.
    """

    def test_tamper_protection_state_is_detectable(self, build_info):
        """Sanity check: we can read the TP registry value without error."""
        if not DefenderAction.supported_on(build_info):
            pytest.skip("DefenderAction not supported on this OS build")

        tp = _tamper_protection_enabled()
        assert isinstance(tp, bool)
        status = "ENABLED" if tp else "DISABLED"
        print(f"\n  Tamper Protection: {status}")

    def test_apply_does_not_raise_when_tamper_protection_on(self, build_info):
        """
        Even if Tamper Protection is active and blocks PowerShell,
        apply() must not raise an exception.
        """
        if not DefenderAction.supported_on(build_info):
            pytest.skip("DefenderAction not supported on this OS build")
        if not _tamper_protection_enabled():
            pytest.skip("Tamper Protection is off — not relevant for this test")

        action = DefenderAction()   # fail_on_error=False (default)
        try:
            action.apply()   # PowerShell will fail silently; registry write proceeds
        finally:
            action.revert()

    def test_realtime_monitoring_actually_disabled_when_tp_off(self, build_info):
        """
        When Tamper Protection is OFF, PowerShell should successfully disable
        real-time monitoring.  Verifies via Get-MpPreference.
        """
        if not DefenderAction.supported_on(build_info):
            pytest.skip("DefenderAction not supported on this OS build")
        if _tamper_protection_enabled():
            pytest.skip(
                "Tamper Protection is ON — PowerShell cannot disable Defender; "
                "disable TP in Security Center first to run this test"
            )

        action = DefenderAction()
        try:
            action.apply()
            rt_on = _realtime_monitoring_enabled()
            assert rt_on is False, (
                f"Expected real-time monitoring OFF after apply, "
                f"Get-MpPreference returned: {rt_on!r}"
            )
        finally:
            action.revert()

    def test_realtime_monitoring_restored_after_revert_when_tp_off(self, build_info):
        """
        When Tamper Protection is OFF, after revert() real-time monitoring
        should be back ON.
        """
        if not DefenderAction.supported_on(build_info):
            pytest.skip("DefenderAction not supported on this OS build")
        if _tamper_protection_enabled():
            pytest.skip(
                "Tamper Protection is ON — skipping PowerShell revert verification"
            )

        action = DefenderAction()
        action.apply()
        action.revert()

        rt_on = _realtime_monitoring_enabled()
        assert rt_on is True, (
            f"Expected real-time monitoring ON after revert, "
            f"Get-MpPreference returned: {rt_on!r}"
        )


# ------------------------------------------------------------------ #
# Diagnostic test — always runs, never fails                         #
# ------------------------------------------------------------------ #

class TestDefenderDiagnostic:
    """
    Diagnostic tests: always report current Defender state.
    Useful for understanding the test environment before running real tests.
    """

    def test_print_defender_environment(self, build_info):
        tp       = _tamper_protection_enabled()
        reg_val  = _read_disable_antispyware()
        rt_on    = _realtime_monitoring_enabled()

        print(
            f"\n  === Defender Environment ===\n"
            f"  Tamper Protection    : {'ON' if tp else 'OFF'}\n"
            f"  DisableAntiSpyware   : {reg_val!r}  (None = key absent)\n"
            f"  RealTime Monitoring  : {'ON' if rt_on else 'OFF' if rt_on is False else 'unknown'}\n"
            f"  supported_on(build)  : {DefenderAction.supported_on(build_info)}\n"
        )
        # Always passes — just prints diagnostics
        assert True
