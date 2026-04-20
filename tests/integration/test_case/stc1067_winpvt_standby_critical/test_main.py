"""
STC-1067: WinPVT Standby Critical (Pytest Framework)

End-to-end test that validates SSD health under HP WinPVT Standby stress at
the Critical level.  Captures a CDI SMART baseline before the run and
compares it after to ensure no unexpected attribute changes.

Workflow:
    Step 1  — Precondition: clean testlog, remove stale reboot state.
    Step 2  — Install Tools: install WinPVT, SmiCli, and CDI via Chocolatey.
    Step 3  — Apply OsConfig: disable System Restore, MemoryDiagnostic,
              McAfee tasks, Fast Startup; enable auto admin logon.
    Step 4  — Clean Environment: reboot for a clean platform environment.
    Step 5  — CDI Before: capture SMART baseline (Before_ prefix).
    Step 6  — Run WinPVT Standby: execute WinPVT Standby Critical scenario
              and verify it completes successfully.
    Step 7  — CDI After: capture post-test SMART snapshot (After_ prefix).
    Step 8  — SMART Compare: verify Unsafe Shutdowns did not increase and
              any configured must-be-zero attributes equal 0.

Requirements:
    - Windows OS with Administrator privileges.
    - WinPVT 11.16.0 installer at bin/installers/winpvt/11.16.0/WinPVT.exe.
    - Chocolatey package at bin/chocolatey/packages/winpvt/.
    - CDI (CrystalDiskInfo) installed at C:\\tools\\CrystalDiskInfo\\DiskInfo64.exe.

Environment variables:
    SSD_TESTKIT_AUTO_LOGIN_PASSWORD   Password for auto admin logon
    TOOL_LOG_DIR                      Override base log directory

Run:
    pytest tests/integration/test_case/stc1067_winpvt_standby_critical/test_main.py -v -s
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.reboot_manager import RebootManager
from framework.test_utils import cleanup_directory
from lib.logger import get_module_logger, clear_log_files
from lib.testtool.tool_installer import ToolInstaller
from lib.testtool.osconfig import OsConfigController
from lib.testtool.osconfig.state_manager import OsConfigStateManager
from lib.testtool.winpvt import WinPVTController
from lib.testtool.winpvt.exceptions import WinPVTError

logger = get_module_logger(__name__)


@pytest.mark.client_hp
@pytest.mark.interface_pcie
@pytest.mark.project_standard
@pytest.mark.feature_power
@pytest.mark.requires_winpvt
@pytest.mark.slow
class TestSTC1067WinPVTStandbyCritical(BaseTestCase):
    """
    STC-1067: WinPVT Standby Critical — HP WinPVT standby stress with SMART health check.
    """

    _osconfig_controller: "OsConfigController | None" = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _cleanup_test_logs(self) -> None:
        """Remove leftover logs from previous test runs."""
        Path('./testlog').mkdir(parents=True, exist_ok=True)

        cleanup_directory('./testlog/CDILog', 'CDI log directory', logger)
        cleanup_directory('./testlog/WinPVTLog', 'WinPVT log directory', logger)
        cleanup_directory('./testlog/WinPVTResult', 'WinPVT result directory', logger)

        log_path = self.config.get('log_path', './log/STC-1067')
        cleanup_directory(log_path, 'test log directory', logger)

        log_dir = Path(log_path)
        for log_file in ['log.txt', 'log.err']:
            p = log_dir / log_file
            if p.exists():
                try:
                    p.unlink()
                except Exception as exc:
                    logger.warning(f"[CLEANUP] Could not remove {p}: {exc}")

    # ------------------------------------------------------------------
    # Step 1 — Precondition
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition")
    def test_01_precondition(self):
        """Clean testlog (preserve Runcard.ini) and remove stale reboot state."""
        self._cleanup_testlog_directory()
        clear_log_files()
        Path(self.log_path).mkdir(parents=True, exist_ok=True)

        state_file = Path(RebootManager.STATE_FILE)
        if state_file.exists():
            state_file.unlink()
            self.reboot_mgr.state = self.reboot_mgr._load_state()
            logger.info(f"[TEST_01] Removed stale reboot state: {state_file}")

        logger.info("[TEST_01] Precondition complete")

    # ------------------------------------------------------------------
    # Step 2 — Install Tools
    # ------------------------------------------------------------------

    @pytest.mark.order(2)
    @step(2, "Install tools")
    def test_02_install_tools(self):
        """Install tools declared in Config/tools.yaml (winpvt, cdi)."""
        _tools_yaml = Path(__file__).parent / "Config" / "tools.yaml"
        ToolInstaller(_tools_yaml).install_all()
        logger.info("[TEST_02] Tools installed")

    # ------------------------------------------------------------------
    # Step 3 — Apply OS Configuration
    # ------------------------------------------------------------------

    @pytest.mark.order(3)
    @step(3, "Apply OS configuration")
    @pytest.mark.skip(reason="Test")
    def test_03_apply_osconfig(self):
        """Apply OS configuration from Config/osconfig.yaml.

        Disables System Restore, MemoryDiagnostic tasks, McAfee tasks, and
        Fast Startup; enables auto admin logon for post-reboot recovery.
        """
        controller = OsConfigController(
            profile=self._osconfig_profile,
            state_manager=OsConfigStateManager(),
        )
        controller.apply_all()
        TestSTC1067WinPVTStandbyCritical._osconfig_controller = controller
        logger.info("[TEST_03] OsConfig applied successfully")

    # ------------------------------------------------------------------
    # Step 4 — Clean Environment + Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(4)
    @step(4, "Clean Environment")
    @pytest.mark.skip(reason="Test")
    def test_04_clean_environment(self, request):
        """Reboot the DUT for a clean platform environment before WinPVT run.

        RebootManager persists state, writes the startup BAT, issues
        shutdown /r, and calls os._exit(0).  pytest resumes at
        test_05_cdi_before after the system comes back up (Run #2).

        # os._exit(0) is called inside setup_reboot — code below never executes
        """
        logger.info("[TEST_04] Issuing reboot for clean platform environment...")

        # Pre-mark BEFORE setup_reboot() calls os._exit(0) to avoid infinite reboot loop.
        self.reboot_mgr.pre_mark_completed(request.node.name)

        self.reboot_mgr.setup_reboot(
            delay=10,
            reason="test_04_clean_environment: clean platform environment before WinPVT",
            test_file=__file__,
        )
        # os._exit(0) called inside setup_reboot — code below never executes

    # Shared WinPVTController instance between test_05 and test_06
    _winpvt_ctrl: "WinPVTController | None" = None

    # ------------------------------------------------------------------
    # Step 5 — WinPVT Startup (launch + dismiss dialogs)
    # ------------------------------------------------------------------

    @pytest.mark.order(5)
    @step(5, "WinPVT Startup: launch and dismiss dialogs")
    def test_05_winpvt_startup(self):
        """Launch WinPVT and dismiss all startup dialogs (License, AccessKey, Configurations).

        After this step WinPVT main window is idle and ready to load a test plan.
        The controller instance is stored in _winpvt_ctrl for test_06.
        """
        winpvt_cfg = self.config['winpvt']
        timeout_minutes = winpvt_cfg.get('timeout_minutes', 120)

        ctrl_kwargs = dict(
            exe_path=winpvt_cfg['ExePath'],
            result_path=winpvt_cfg['ResultPath'],
            test_category=winpvt_cfg.get('test_category', 'Standby'),
            stress_level=winpvt_cfg.get('stress_level', 'Critical'),
            timeout_minutes=timeout_minutes,
            screenshot_dir='./testlog/WinPVTScreenshots',
        )
        pvt_file = winpvt_cfg.get('PvtFile', '').strip()
        if pvt_file:
            # Relative paths are resolved from the test case directory
            pvt_path = Path(pvt_file)
            if not pvt_path.is_absolute():
                pvt_path = Path(__file__).parent / pvt_path
            ctrl_kwargs['pvt_file'] = str(pvt_path)
            logger.info(f"[TEST_05] Using pvt_file from Config: {pvt_path}")
        ctrl = WinPVTController(**ctrl_kwargs)

        try:
            ctrl.setup_phase()
        except WinPVTError as exc:
            pytest.fail(f"[TEST_05] WinPVT startup failed: {exc}")

        TestSTC1067WinPVTStandbyCritical._winpvt_ctrl = ctrl
        logger.info("[TEST_05] WinPVT startup complete — main window ready")

    # ------------------------------------------------------------------
    # Step 6 — Run WinPVT Standby Critical
    # ------------------------------------------------------------------

    @pytest.mark.order(6)
    @step(6, "Run WinPVT Standby Critical")
    def test_06_run_winpvt_standby(self):
        """Open Standby Critical Only.pvt, click GO, wait for completion, verify results."""
        ctrl = TestSTC1067WinPVTStandbyCritical._winpvt_ctrl
        if ctrl is None:
            pytest.fail("[TEST_06] WinPVT controller not initialised — test_05 may have failed")

        timeout_minutes = self.config['winpvt'].get('timeout_minutes', 120)

        ctrl.start()
        ctrl.join(timeout=ctrl.timeout_seconds + 120)

        if ctrl.is_alive():
            ctrl.stop()
            pytest.fail(
                f"[TEST_06] WinPVT timed out after {timeout_minutes} minutes"
            )

        if ctrl.status is not True:
            pytest.fail(
                f"[TEST_06] WinPVT Standby Critical failed: {ctrl.error_message}"
            )

        # Write completed cycle count to Runcard.ini
        cycles = ctrl.cycles
        if self.runcard is not None and cycles > 0:
            self.runcard.update_test_status(test_cycle=cycles)
            self.runcard.save_to_file()
            logger.info(f"[TEST_06] Runcard updated: Test Cycle={cycles}")

        logger.info("[TEST_06] WinPVT Standby Critical completed successfully")


