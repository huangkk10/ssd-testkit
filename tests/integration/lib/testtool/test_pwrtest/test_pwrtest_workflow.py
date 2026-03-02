"""
PwrTest Controller Integration Tests

These tests run against a REAL pwrtest.exe on a real Windows machine.
Nothing is mocked.

Requirements
------------
- pwrtest.exe present (set PWRTEST_EXE_PATH or use default path)
- Real Windows environment with ACPI sleep support
- Elevated (Administrator) privileges

Environment-variable overrides
-------------------------------
PWRTEST_EXE_PATH       Full path to pwrtest.exe
PWRTEST_OS_NAME        win7 | win10 | win11  (default win11)
PWRTEST_OS_VERSION     e.g. 25H2, 2004       (default 25H2)
PWRTEST_CYCLE_COUNT    Number of sleep cycles (default 1)
PWRTEST_WAKE_AFTER     Wake delay in seconds  (default 30)
PWRTEST_LOG_DIR        Base directory for output
PWRTEST_TIMEOUT        Per-test timeout (s)   (default 300)

Run integration tests only
--------------------------
    pytest tests/integration/lib/testtool/test_pwrtest/ -v -m "integration"

Skip all integration tests
--------------------------
    pytest ... -m "not integration"
"""

import sys
import threading
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.testtool.pwrtest import PwrTestController
from lib.testtool.pwrtest.exceptions import PwrTestError


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_controller(env: dict, log_dir: Path, **extra) -> PwrTestController:
    """Build a PwrTestController for a given test run."""
    kwargs = {
        'pwrtest_base_dir':  env['pwrtest_base_dir'],
        'os_name':           env['os_name'],
        'os_version':        env['os_version'],
        'cycle_count':       env['cycle_count'],
        'delay_seconds':     env['delay_seconds'],
        'wake_after_seconds':env['wake_after_seconds'],
        'log_path':          str(log_dir),
        'timeout_seconds':   env['timeout'],
    }
    # If an explicit exe path is set, override auto-composition
    if env.get('executable_path'):
        kwargs['executable_path'] = env['executable_path']
    kwargs.update(extra)
    return PwrTestController(**kwargs)


# ---------------------------------------------------------------------------
# Integration test class
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_pwrtest
@pytest.mark.slow
class TestPwrTestControllerIntegration:
    """End-to-end PwrTestController tests against real pwrtest.exe."""

    @pytest.mark.timeout(400)
    def test_t01_full_workflow_single_cycle(
        self,
        pwrtest_env,
        check_environment,
        clean_log_dir,
    ):
        """
        T01 — Run one sleep/resume cycle and verify PASS result.

        The test system must support S3 (or S0ix) sleep and have a working
        RTC wake alarm.  pwrtest.exe will put the machine to sleep for
        ``wake_after_seconds`` seconds then resume and report.
        """
        ctrl = _make_controller(pwrtest_env, clean_log_dir)
        ctrl.start()
        ctrl.join(timeout=pwrtest_env['timeout'])

        assert ctrl.status is True, (
            f"PwrTest reported status={ctrl.status}. "
            f"Summary: {ctrl.result_summary}"
        )
        assert ctrl.result_summary.get('completed_cycles', 0) == pwrtest_env['cycle_count']

    @pytest.mark.timeout(60)
    def test_t02_stop_signal_terminates_gracefully(
        self,
        pwrtest_env,
        check_environment,
        clean_log_dir,
    ):
        """
        T02 — Verify stop() terminates the controller and process cleanly.

        Uses a very long wake time so the process is still sleeping when
        stop() fires.  The test expects status to be set (True or False),
        never None.
        """
        # Use a long wake time to ensure the process is still running
        env_long = dict(pwrtest_env)
        env_long['wake_after_seconds'] = 120
        env_long['timeout'] = 300

        ctrl = _make_controller(env_long, clean_log_dir)
        ctrl.start()

        # Stop the controller after 5 seconds (process will still be sleeping)
        stop_timer = threading.Timer(5.0, ctrl.stop)
        stop_timer.start()

        ctrl.join(timeout=30)
        stop_timer.cancel()

        # status must be set — either False (stopped early) or any truthy value
        assert ctrl.status is not None, (
            "status should be set after stop() + join()"
        )

    @pytest.mark.timeout(400)
    def test_t03_log_files_created_in_log_dir(
        self,
        pwrtest_env,
        check_environment,
        clean_log_dir,
    ):
        """
        T03 — Verify that pwrtestlog.log is created in the configured log_path.
        """
        ctrl = _make_controller(pwrtest_env, clean_log_dir)
        ctrl.start()
        ctrl.join(timeout=pwrtest_env['timeout'])

        log_file = clean_log_dir / 'pwrtestlog.log'
        assert log_file.exists(), (
            f"pwrtestlog.log not found in '{clean_log_dir}'. "
            "Check that log_path is writable and pwrtest.exe ran successfully."
        )

    @pytest.mark.timeout(400)
    def test_t04_result_summary_populated(
        self,
        pwrtest_env,
        check_environment,
        clean_log_dir,
    ):
        """
        T04 — Verify result_summary contains expected keys after run.
        """
        ctrl = _make_controller(pwrtest_env, clean_log_dir)
        ctrl.start()
        ctrl.join(timeout=pwrtest_env['timeout'])

        summary = ctrl.result_summary
        for key in ('status', 'cycles_attempted', 'cycles_passed', 'errors', 'log_path'):
            assert key in summary, f"result_summary missing key: '{key}'"
