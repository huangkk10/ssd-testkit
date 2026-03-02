"""
PHM Controller Integration Tests

Tests run against the REAL PHM installation on a real Windows machine.
Nothing is mocked.  Tests are organized in 6 phases (see PHM_PLAN.md §5.2).

Requirements
------------
- Windows environment (PHM is Windows-only)
- Run as Administrator
- PHM installer at tests/integration/bin/PHM/ (Phase 1)
  or PHM already installed (Phase 2+)

Environment-variable overrides
-------------------------------
PHM_INSTALLER_PATH    path to phm_nda_*.exe
PHM_INSTALL_DIR       PHM installation directory
PHM_LOG_DIR           base log directory
PHM_TIMEOUT           per-test timeout in seconds

Run all integration tests
-------------------------
    pytest tests/integration/lib/testtool/test_phm/ -v -m "integration"

Run a single phase
------------------
    pytest tests/integration/lib/testtool/test_phm/ -v -k "TestPHMInstallation"
    pytest tests/integration/lib/testtool/test_phm/ -v -k "TestPHMLaunch"
    pytest tests/integration/lib/testtool/test_phm/ -v -k "TestPHMUIConfig"
    pytest tests/integration/lib/testtool/test_phm/ -v -k "TestPHMRun"
    pytest tests/integration/lib/testtool/test_phm/ -v -k "TestPHMLogParser"
    pytest tests/integration/lib/testtool/test_phm/ -v -k "TestPHMFullWorkflow"

Skip integration tests
----------------------
    pytest ... -m "not integration"
"""

import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.testtool.phm import PHMController, PHMConfig, PHMLogParser
from lib.testtool.phm.process_manager import PHMProcessManager
from lib.testtool.phm.exceptions import PHMError, PHMInstallError


# Helper ---------------------------------------------------------------

def _make_pm(phm_env) -> PHMProcessManager:
    return PHMProcessManager(
        install_path=phm_env['install_path'],
        executable_name=phm_env['executable_name'],
    )


def _make_controller(phm_env, log_dir, **extra) -> PHMController:
    return PHMController(
        installer_path=phm_env['installer_path'],
        install_path=phm_env['install_path'],
        log_path=str(log_dir),
        cycle_count=phm_env['cycle_count'],
        test_duration_minutes=phm_env['test_duration_minutes'],
        enable_modern_standby=phm_env['enable_modern_standby'],
        timeout=phm_env['timeout'],
        **extra,
    )


# ======================================================================
# Phase 1 — Installation / Uninstallation
# ======================================================================

@pytest.mark.integration
@pytest.mark.requires_phm
class TestPHMInstallation:
    """
    Phase 1: Verify PHM can be silently installed and uninstalled.
    Prerequisite: installer present at tests/integration/bin/PHM/.
    """

    def test_clean_install(self, phm_env, check_installer, clean_log_dir):
        """Install PHM from scratch; verify executable is present afterward."""
        pm = _make_pm(phm_env)

        # Start from a clean state
        if pm.is_installed():
            pm.uninstall(timeout=120)
            time.sleep(2)

        assert not pm.is_installed(), "PHM should not be installed before test"

        result = pm.install(
            installer_path=phm_env['installer_path'],
            timeout=600,
        )
        assert result is True, "install() should return True"
        assert pm.is_installed(), "PHM should be installed after install()"

    def test_reinstall_is_idempotent(self, phm_env, check_installer, clean_log_dir):
        """Installing when already installed should not raise."""
        pm = _make_pm(phm_env)
        if not pm.is_installed():
            pm.install(installer_path=phm_env['installer_path'], timeout=600)

        # Second install should succeed (or at minimum not raise)
        result = pm.install(
            installer_path=phm_env['installer_path'],
            timeout=600,
        )
        assert result is True

    def test_uninstall(self, phm_env, check_installer, clean_log_dir):
        """Uninstall PHM; verify executable is gone afterward."""
        pm = _make_pm(phm_env)
        if not pm.is_installed():
            pm.install(installer_path=phm_env['installer_path'], timeout=600)

        result = pm.uninstall(timeout=120)
        assert result is True, "uninstall() should return True"

        time.sleep(2)
        assert not pm.is_installed(), "PHM should not be installed after uninstall()"


# ======================================================================
# Phase 2 — Launch / Terminate
# ======================================================================

@pytest.mark.integration
@pytest.mark.requires_phm
class TestPHMLaunch:
    """
    Phase 2: Verify PHM GUI can be launched and terminated.
    Prerequisite: PHM is installed (Phase 1 must have run).
    """

    def test_launch_gui(self, phm_env, check_environment, clean_log_dir):
        """PHM main process starts and PID is assigned."""
        pm = _make_pm(phm_env)
        proc = pm.launch()
        try:
            assert pm.pid is not None, "PID should be set after launch()"
            assert pm.is_running(), "Process should be running after launch()"
        finally:
            pm.terminate(timeout=15)

    def test_process_terminate_clean(self, phm_env, check_environment, clean_log_dir):
        """terminate() should stop the process without leaving it orphaned."""
        pm = _make_pm(phm_env)
        pm.launch()
        time.sleep(2)
        pm.terminate(timeout=15)

        time.sleep(1)
        assert not pm.is_running(), "Process should not be running after terminate()"
        assert pm.pid is None, "PID should be cleared after terminate()"


# ======================================================================
# Phase 3 — UI Parameter Configuration
# ======================================================================

@pytest.mark.integration
@pytest.mark.requires_phm
@pytest.mark.slow
class TestPHMUIConfig:
    """
    Phase 3: Set test parameters via the PHM GUI.
    Prerequisite: PHM is installed and GUI can be launched.

    .. note::
        These tests depend on correct UI control identifiers in
        ``lib/testtool/phm/ui_monitor.py``.  Update the ``_EDIT_*`` /
        ``_CHK_*`` / ``_BTN_*`` constants after inspecting the real window.
    """

    def test_set_cycle_count(self, phm_env, check_environment, clean_log_dir):
        """Cycle count can be set in the PHM UI."""
        from lib.testtool.phm.ui_monitor import PHMUIMonitor

        pm = _make_pm(phm_env)
        pm.launch()
        try:
            monitor = PHMUIMonitor()
            monitor.wait_for_window(timeout=30)
            monitor.set_cycle_count(3)
            monitor.disconnect()
        finally:
            pm.terminate(timeout=15)

    def test_set_duration(self, phm_env, check_environment, clean_log_dir):
        """Test duration can be set in the PHM UI."""
        from lib.testtool.phm.ui_monitor import PHMUIMonitor

        pm = _make_pm(phm_env)
        pm.launch()
        try:
            monitor = PHMUIMonitor()
            monitor.wait_for_window(timeout=30)
            monitor.set_test_duration(1)  # 1 minute
            monitor.disconnect()
        finally:
            pm.terminate(timeout=15)

    def test_set_modern_standby(self, phm_env, check_environment, clean_log_dir):
        """Modern Standby checkbox can be toggled."""
        from lib.testtool.phm.ui_monitor import PHMUIMonitor

        pm = _make_pm(phm_env)
        pm.launch()
        try:
            monitor = PHMUIMonitor()
            monitor.wait_for_window(timeout=30)
            monitor.set_modern_standby_mode(True)
            monitor.set_modern_standby_mode(False)  # toggle back
            monitor.disconnect()
        finally:
            pm.terminate(timeout=15)


# ======================================================================
# Phase 4 — Short Run
# ======================================================================

@pytest.mark.integration
@pytest.mark.requires_phm
@pytest.mark.slow
class TestPHMRun:
    """
    Phase 4: Execute a short PHM test (smoke test).
    Prerequisite: PHM is installed and UI controls are verified.
    """

    @pytest.mark.timeout(900)
    def test_short_run(self, phm_env, check_environment, clean_log_dir):
        """
        Run 1 cycle with a short duration; verify status is set and not None.
        """
        ctrl = _make_controller(
            phm_env, clean_log_dir,
            cycle_count=1,
            test_duration_minutes=1,
            timeout=600,
        )
        ctrl.start()
        ctrl.join(timeout=600)

        assert ctrl.status is not None, "status must be set (True or False) after run"

    @pytest.mark.timeout(60)
    def test_stop_during_run(self, phm_env, check_environment, clean_log_dir):
        """Calling stop() mid-run should terminate cleanly (status not None)."""
        import threading

        ctrl = _make_controller(
            phm_env, clean_log_dir,
            cycle_count=10,
            test_duration_minutes=60,
            timeout=300,
        )
        ctrl.start()
        threading.Timer(10.0, ctrl.stop).start()
        ctrl.join(timeout=60)

        assert ctrl.status is not None, "status must be set after stop()"


# ======================================================================
# Phase 5 — Log Parsing (real HTML)
# ======================================================================

@pytest.mark.integration
@pytest.mark.requires_phm
class TestPHMLogParser:
    """
    Phase 5: Parse real HTML reports generated by Phase 4.
    Prerequisite: At least one PHM run has completed and produced an HTML log.
    """

    def test_parse_real_html_from_log_dir(self, phm_env, log_dir):
        """Batch parse all HTML files in the session log dir."""
        parser = PHMLogParser()
        results = parser.parse_html_reports_batch(str(log_dir))

        if not results:
            pytest.skip(
                "No HTML reports found in log_dir. "
                "Run TestPHMRun tests first."
            )

        for result in results:
            assert result.status in ('PASS', 'FAIL', 'UNKNOWN')
            assert result.raw_html_path != ''

    def test_summary_structure(self, phm_env, log_dir):
        """PHMLogParser.summarize() returns expected keys."""
        parser = PHMLogParser()
        results = parser.parse_html_reports_batch(str(log_dir))

        if not results:
            pytest.skip("No HTML reports found.")

        summary = PHMLogParser.summarize(results)
        assert 'total' in summary
        assert 'pass' in summary
        assert 'fail' in summary
        assert 'error_summary' in summary
        assert summary['total'] == len(results)


# ======================================================================
# Phase 6 — Full E2E Workflow
# ======================================================================

@pytest.mark.integration
@pytest.mark.requires_phm
@pytest.mark.slow
class TestPHMFullWorkflow:
    """
    Phase 6: Full end-to-end test.
    install → configure UI → run → parse log → uninstall
    """

    @pytest.mark.timeout(1200)
    def test_install_run_parse_uninstall(
        self, phm_env, check_installer, clean_log_dir
    ):
        """
        E2E: Install PHM → run 1 short cycle → parse HTML → uninstall.
        """
        pm = _make_pm(phm_env)

        # 1. Fresh install
        if pm.is_installed():
            pm.uninstall(timeout=120)
            time.sleep(2)
        pm.install(installer_path=phm_env['installer_path'], timeout=600)
        assert pm.is_installed()

        # 2. Run a short test via controller
        ctrl = _make_controller(
            phm_env, clean_log_dir,
            cycle_count=1,
            test_duration_minutes=1,
            timeout=600,
        )
        ctrl.start()
        ctrl.join(timeout=600)

        assert ctrl.status is not None, "PHM controller must set status"

        # 3. Parse HTML report
        parser = PHMLogParser()
        results = parser.parse_html_reports_batch(str(clean_log_dir))
        # Note: report may be in configured log_path rather than clean_log_dir
        # depending on how PHM writes logs; adjust if needed

        # 4. Uninstall
        uninstall_result = pm.uninstall(timeout=120)
        assert uninstall_result is True

        time.sleep(2)
        assert not pm.is_installed(), "PHM must be uninstalled at end of E2E test"
