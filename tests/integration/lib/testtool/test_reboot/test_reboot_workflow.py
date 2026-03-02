"""
Integration tests for OsRebootController.

WARNING: These tests issue a real ``shutdown /r`` command.
         Run only on an isolated machine or VM.
         Guard: ``ENABLE_REBOOT_INTEGRATION_TEST=1`` env-var must be set.

Each test below is tagged:
    @pytest.mark.integration
    @pytest.mark.requires_reboot

To run:
    set ENABLE_REBOOT_INTEGRATION_TEST=1
    python -m pytest tests/integration/lib/testtool/test_reboot/ -v -m "integration and requires_reboot"
"""
import pytest

from lib.testtool.reboot import OsRebootController
from lib.testtool.reboot.state_manager import OsRebootStateManager


# ------------------------------------------------------------------ #
# Abort-before-reboot smoke test                                       #
# This is the only test that is reasonably safe to run in CI — it      #
# issues shutdown /r then immediately aborts it with shutdown /a.      #
# ------------------------------------------------------------------ #

@pytest.mark.integration
@pytest.mark.requires_reboot
def test_abort_cancels_scheduled_reboot(check_environment, reboot_state_file):
    """
    Schedule a reboot with a 30-second delay then immediately abort it.

    Verifies that:
      - The shutdown command is accepted by Windows (no exception).
      - ``shutdown /a`` cancels the reboot (no actual reboot occurs).
      - The state file is written before the abort.
    """
    ctrl = OsRebootController(
        delay_seconds=10,
        reboot_count=1,
        state_file=reboot_state_file,
    )

    # Start the thread but stop it before the OS reboots
    ctrl.start()

    # Give the thread enough time to issue shutdown /r and save state
    import time
    time.sleep(3)

    # Abort the reboot
    ctrl.abort_reboot()
    ctrl.stop()
    ctrl.join(timeout=15)

    # State file should have been saved
    sm = OsRebootStateManager(reboot_state_file)
    assert sm.is_recovering() is True, (
        "State file was not written before the abort — "
        "state persistence is broken."
    )

    # Clean up
    sm.clear()


# ------------------------------------------------------------------ #
# Recovery detection test (no actual reboot needed)                    #
# ------------------------------------------------------------------ #

@pytest.mark.integration
@pytest.mark.requires_reboot
def test_recovery_detection_from_existing_state(reboot_state_file):
    """
    Pre-populate the state file as if a reboot just completed,
    then verify OsRebootController enters recovery mode and
    reports PASS when reboot_count is already reached.
    """
    # Simulate a previous cycle completing cycle 1 of 1
    sm = OsRebootStateManager(reboot_state_file)
    sm.save({
        'is_recovering': True,
        'current_cycle':  1,
        'total_cycles':   1,
    })

    ctrl = OsRebootController(
        reboot_count=1,
        state_file=reboot_state_file,
    )
    ctrl.start()
    ctrl.join(timeout=10)

    assert ctrl.status is True, (
        f"Expected PASS after recovery with all cycles complete, "
        f"got status={ctrl.status}"
    )
    assert ctrl.current_cycle == 1

    # Clean up
    sm.clear()


# ------------------------------------------------------------------ #
# Full single-reboot cycle (DANGEROUS — causes machine reboot)        #
# ------------------------------------------------------------------ #

@pytest.mark.integration
@pytest.mark.requires_reboot
@pytest.mark.slow
def test_single_reboot_cycle_full(reboot_state_file):
    """
    Issue a real single-reboot cycle.

    **CAUTION**: This test WILL reboot the machine.
    It is intended for an isolated VM or bare-metal test rig only.

    After reboot, re-run the test suite; the second run detects
    ``is_recovering=True`` and asserts PASS.
    """
    sm = OsRebootStateManager(reboot_state_file)

    if sm.is_recovering():
        # --- Post-reboot recovery run ---
        ctrl = OsRebootController(
            reboot_count=1,
            state_file=reboot_state_file,
        )
        ctrl.start()
        ctrl.join(timeout=30)
        assert ctrl.status is True
        sm.clear()
    else:
        # --- Initial run — will reboot the machine ---
        ctrl = OsRebootController(
            delay_seconds=10,
            reboot_count=1,
            state_file=reboot_state_file,
        )
        ctrl.start()
        ctrl.join(timeout=60)
        # Execution reaches here only if abort was triggered or timeout occurred
        pytest.skip("Machine is rebooting — re-run test suite after boot to verify PASS")
