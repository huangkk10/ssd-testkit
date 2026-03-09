"""
STC-2562: Modern Standby Integration Test

Tests SSD health and compatibility under Windows Modern Standby (ACPI S0ix)
using the PHM (Powerhouse Mountain) toolchain.

Test Flow:
    Phase A — Pre-Reboot 1:
    1. Precondition  — create log directories
    2. CDI Before    — SMART baseline
    3. Install PHM   — silent installer
    4. PEPChecker    — run NDA collector, collect logs
    5. Clear Sleep Study history & Reboot — clean slate before PwrTest

    Phase B1 — Post-Reboot 1:
    6. PwrTest       — sleep/wake cycle + collect sleepstudy
    7. Verify sleep  — SW/HW DRIPS >= 90 %
    8. OsConfig      — apply OS settings
    9. Clear Sleep Study history & Reboot — schedule reboot, terminate session

    Phase B2 — Post-Reboot 2:
    10. PHM collector — run Modern Standby Cycling scenario
    11. Verify DRIPS  — generate sleepstudy report; SW/HW DRIPS > 80%
    12. CDI After    — SMART snapshot
    13. SMART check  — Unsafe Shutdowns unchanged; error counters == 0
"""

import sys
import os
import shutil
import time
import json
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
# tests/integration/client_pcie_lenovo_storagedv/stc2562_modern_standby/test_main.py
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.test_utils import cleanup_directory
from lib.testtool import RunCard as RC
from lib.testtool.cdi import CDIController
from lib.testtool.phm import (
    PHMController,
    PEPChecker,
    PHMPEPCheckerError,
)
from lib.testtool.phm.process_manager import PHMProcessManager
from lib.testtool.phm.ui_monitor import PHMUIMonitor
from lib.testtool.phm.collector_session import CollectorSession
from lib.testtool.phm.scenarios.modern_standby_cycling import ModernStandbyCyclingParams
from lib.testtool.phm.exceptions import PHMInstallError
from lib.testtool.pwrtest import PwrTestController
from lib.testtool.pwrtest.config import PwrTestScenario
from lib.testtool.sleepstudy import SleepStudyController
from lib.testtool.sleepstudy.sleep_report_parser import SleepReportParser
from lib.testtool.sleepstudy.history_cleaner import SleepHistoryCleaner
from lib.testtool.osconfig import OsConfigController
from lib.testtool.osconfig.config import OsConfigProfile
from lib.logger import get_module_logger, logConfig
from framework.reboot_manager import RebootManager

logger = get_module_logger(__name__)

# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.client_lenovo
@pytest.mark.interface_pcie
@pytest.mark.project_storagedv
@pytest.mark.feature_modern_standby
@pytest.mark.slow
class TestSTC2562ModernStandby(BaseTestCase):
    """
    STC-2562: Modern Standby Test for Lenovo StorageDV (PCIe)
    """

    # Class-level state shared between steps
    _pre_sleep_time: str = ""
    _post_sleep_time: str = ""
    _phm_start_time: str = ""
    _phm_end_time: str = ""
    _osconfig_controller: "OsConfigController | None" = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _remove_existing_phm(self) -> bool:
        """
        Uninstall Powerhouse Mountain (PHM) if it is currently installed.

        Uses PHMController.is_installed() / uninstall() so that the same
        install-path configured in Config.json is used for detection.

        If the standard uninstaller cannot be found (PHMInstallError), falls
        back to force-killing any running PHM process and returns True —
        step 03 will perform a fresh install regardless.

        Returns:
            True always (hard failures are logged as warnings, not test failures).
        """
        phm_cfg = self.config['phm']
        ctrl = PHMController(
            installer_path=phm_cfg['installer'],
            install_path=phm_cfg['install_path'],
        )

        if not ctrl.is_installed():
            logger.info("[_remove_existing_phm] PHM is not installed — nothing to remove")
            return True

        logger.info("[_remove_existing_phm] PHM found — starting uninstall")
        try:
            ctrl.uninstall()
            logger.info("[_remove_existing_phm] PHM uninstalled successfully")
            return True
        except PHMInstallError as exc:
            # No uninstaller entry found (e.g. previous install left files on
            # disk without a valid registry entry).  Kill all PHM processes
            # first, then remove the entire install directory so that
            # is_installed() returns False and test_03 can do a clean install.
            logger.warning(
                f"[_remove_existing_phm] Uninstaller not found ({exc}) — "
                "force-killing PHM processes and removing install directory"
            )
            mgr = PHMProcessManager(install_path=phm_cfg['install_path'])
            mgr.kill_by_name('PowerhouseMountain.exe')
            install_dir = Path(phm_cfg['install_path'])
            if install_dir.exists():
                try:
                    shutil.rmtree(str(install_dir))
                    logger.info(
                        f"[_remove_existing_phm] Removed install directory: {install_dir}"
                    )
                except Exception as rmex:
                    logger.warning(
                        f"[_remove_existing_phm] Could not remove install directory "
                        f"({install_dir}): {rmex} — installer may still detect PHM"
                    )
            logger.info("[_remove_existing_phm] PHM removed — continuing")
            return True
        except Exception as exc:
            logger.error(f"[_remove_existing_phm] Uninstall failed: {exc}")
            return False

    def _skip_if_not_rebooted(self, min_count: int = 1) -> None:
        """pytest.skip when the required number of reboots has not occurred yet."""
        if self.reboot_mgr.state.get("reboot_count", 0) < min_count:
            pytest.skip(f"Post-reboot step — reboot_count < {min_count}")

    def _cleanup_test_logs(self) -> None:
        """
        Remove leftover logs from previous test runs.

        Cleans:
        1. CDI logs  (testlog/CDILog/)
        2. SleepStudy report  (testlog/sleepstudy-report.html)
        3. PEPChecker logs  (testlog/PEPChecker_Log/)
        4. PwrTest logs  (testlog/PwrTestLog/)
        5. Test-specific log files  (log/STC-2562/log.txt, log.err, ...)
        """
        logger.info("[_cleanup_test_logs] Starting test log cleanup")

        # Ensure base testlog dir exists before any cleanup attempts
        Path('./testlog').mkdir(parents=True, exist_ok=True)

        # 0. Reboot state file — must be removed so the next full run
        #    starts fresh without any completed tests recorded.
        state_file = Path(RebootManager.STATE_FILE)
        if state_file.exists():
            state_file.unlink()
            logger.info(f"[_cleanup_test_logs] Removed reboot state file: {state_file}")

        # 1. CDI logs
        cleanup_directory('./testlog/CDILog', 'CDI log directory', logger)

        # 2. SleepStudy HTML report
        ss_cfg = self.config.get('sleepstudy', {})
        ss_report = Path(ss_cfg.get('output_path', './testlog/sleepstudy-report.html'))
        if ss_report.exists():
            ss_report.unlink()
            logger.info(f"[_cleanup_test_logs] Removed sleepstudy report: {ss_report}")
        else:
            logger.info(f"[_cleanup_test_logs] No sleepstudy report to remove: {ss_report}")

        # 3. PEPChecker logs
        cleanup_directory('./testlog/PEPChecker_Log', 'PEPChecker log directory', logger)

        # 4. PwrTest logs
        cleanup_directory('./testlog/PwrTestLog', 'PwrTest log directory', logger)

        # 5. Test-specific log directory
        log_path = self.config.get('log_path', './log/STC-2562')
        cleanup_directory(log_path, 'test log directory', logger)

        # 5a. Explicitly remove log.txt and log.err from test log directory
        #     (in case cleanup_directory left them behind)
        log_dir = Path(log_path)
        for log_file in ['log.txt', 'log.err']:
            log_file_path = log_dir / log_file
            if log_file_path.exists():
                try:
                    log_file_path.unlink()
                    logger.info(f"[_cleanup_test_logs] Removed log file: {log_file_path}")
                except Exception as exc:
                    logger.warning(f"[_cleanup_test_logs] Could not remove {log_file_path}: {exc}")

        logger.info("[_cleanup_test_logs] Cleanup complete")

    # ------------------------------------------------------------------
    # Fixture
    # ------------------------------------------------------------------

    @pytest.fixture(scope="class", autouse=True)
    def setup_test_class(self, request, testcase_config, runcard_params):
        """Load configuration and initialize test class (runs before all tests)."""
        cls = request.cls
        cls.original_cwd = os.getcwd()

        # Resolve test directory (packaged vs development)
        try:
            from path_manager import path_manager
            test_dir = path_manager.app_dir
            logger.info(f"[SETUP] Packaged environment: {test_dir}")
        except ImportError:
            test_dir = Path(__file__).parent
            logger.info(f"[SETUP] Development environment: {test_dir}")

        os.chdir(test_dir)

        logConfig()

        cls.config = testcase_config.tool_config
        cls.bin_path = testcase_config.bin_directory

        # ── Initialize RebootManager (must be after os.chdir to correct cwd) ───────────
        cls.reboot_mgr = RebootManager(total_tests=13)

        phase = "POST-REBOOT (recovering)" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
        logger.info(f"[SETUP] Phase: {phase}")
        logger.info(f"[SETUP] Test case: {testcase_config.case_id}  version: {testcase_config.case_version}")
        logger.info(f"[SETUP] Working directory: {test_dir}")

        # RunCard integration
        cls.runcard = None
        try:
            cls.runcard = RC.Runcard(**runcard_params['initialization'])
            cls.runcard.start_test(**runcard_params['start_params'])
            logger.info("[RunCard] Started")
        except Exception as exc:
            logger.warning(f"[RunCard] Init failed — {exc} (continuing)")
            cls.runcard = None

        yield

        # Record final RunCard result
        if cls.runcard:
            try:
                failed = request.session.testsfailed > 0
                if not failed:
                    cls.runcard.end_test(RC.TestResult.PASS.value)
                else:
                    cls.runcard.end_test(
                        RC.TestResult.FAIL.value,
                        f"{request.session.testsfailed} test(s) failed",
                    )
            except Exception as exc:
                logger.error(f"[RunCard] end_test failed — {exc}")

        # Revert OS configuration changes applied in test_07 (best-effort)
        if cls._osconfig_controller is not None:
            try:
                logger.info("[TEARDOWN] Reverting OsConfig changes...")
                cls._osconfig_controller.revert_all()
                logger.info("[TEARDOWN] OsConfig reverted successfully")
            except Exception as exc:
                logger.warning(f"[TEARDOWN] OsConfig revert failed — {exc} (continuing)")

        # Clean up RebootManager state file and auto-run BAT (best-effort)
        try:
            cls.reboot_mgr.cleanup()
        except Exception as exc:
            logger.warning(f"[TEARDOWN] RebootManager cleanup failed — {exc} (continuing)")

        logger.info("STC-2562 session complete")
        os.chdir(cls.original_cwd)

    # ------------------------------------------------------------------
    # Phase A — Pre-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @pytest.mark.skip(reason="Currently blocked by PHM instability — will re-enable once PHM is testable")
    @step(1, "Precondition — cleanup and create log directories")
    def test_01_precondition(self):
        """
        Precondition setup:
        1. Remove existing PHM installation (clean slate)
        2. Clean up leftover logs from previous runs
        3. Create fresh log directory structure
        """
        logger.info("[TEST_01] Precondition setup started")

        # Step 1: Remove existing PHM installation
        if not self._remove_existing_phm():
            pytest.fail("Failed to remove existing PHM installation")

        # Step 2: Clean up logs from previous runs
        self._cleanup_test_logs()

        # Step 3: Re-create fresh log directories
        for d in [
            './testlog',
            './testlog/CDILog',
            './testlog/PEPChecker_Log',
            './testlog/PwrTestLog',
            self.config.get('log_path', './log/STC-2562'),
        ]:
            Path(d).mkdir(parents=True, exist_ok=True)
            logger.info(f"[TEST_01] Directory ready: {d}")

        logger.info("[TEST_01] Precondition complete")

    @pytest.mark.order(2)
    @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")
    @step(2, "CDI Before — SMART baseline")
    def test_02_cdi_before(self):
        """Run CrystalDiskInfo to capture SMART baseline (Before_ prefix)."""
        logger.info("[TEST_02] CDI Before started")

        cfg = self.config['cdi']
        ctrl = CDIController(
            executable_path=cfg['ExePath'],
            log_path=cfg['LogPath'],
            log_prefix='Before_',
            screenshot_drive_letter=cfg.get('ScreenShotDriveLetter', 'C:'),
        )
        ctrl.start()
        ctrl.join(timeout=180)

        if not ctrl.status:
            pytest.fail(f"CDI Before failed (status={ctrl.status})")

        logger.info("[TEST_02] CDI Before complete")

    @pytest.mark.order(3)
    @pytest.mark.skip(reason="Currently blocked by PHM instability — will re-enable once PHM is testable")
    @step(3, "Install PHM tool")
    def test_03_install_phm(self):
        """Install Powerhouse Mountain (PHM) tool silently."""
        logger.info("[TEST_03] PHM install started")

        cfg = self.config['phm']
        ctrl = PHMController(
            installer_path=cfg['installer'],
            install_path=cfg['install_path'],
        )

        if ctrl.is_installed():
            logger.info("[TEST_03] PHM already installed — skip install step")
        else:
            ctrl.install()

        assert ctrl.is_installed(), "PHM installation not detected after install"
        logger.info("[TEST_03] PHM install complete")

    @pytest.mark.order(4)
    @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")
    @step(4, "PEPChecker — run NDA collector")
    def test_04_run_pep_checker(self):
        """
        Execute PEPChecker.exe, verify 4 output files, and collect them into
        testlog/PEPChecker_Log/.

        Output files: PBC-Report.html, PBC-sleepstudy-report.html,
                      PBC-Debug-Log.txt, PBC-Errors.txt
        """
        logger.info("[TEST_04] PEPChecker started")

        cfg = self.config['pep_checker']
        checker = PEPChecker(
            exe_path=cfg['exe_path'],
            log_dir=cfg['log_dir'],
            timeout=cfg.get('timeout', 120),
        )

        try:
            result = checker.run_and_collect()
        except PHMPEPCheckerError as exc:
            pytest.fail(f"PEPChecker failed: {exc}")

        # Verify all collected files exist
        for path_attr in ('report_html', 'sleep_report_html', 'debug_log', 'errors_log'):
            p = getattr(result, path_attr)
            assert Path(p).exists(), f"PEPChecker output missing: {path_attr} -> {p}"
            logger.info(f"[TEST_04] Collected: {p}")

        logger.info("[TEST_04] PEPChecker complete")

    @pytest.mark.order(5)
    # @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")
    @step(5, "Clear Sleep Study history & Reboot device")
    def test_05_clear_sleep_history(self, request):
        """
        Clear accumulated Sleep Study history so that the subsequent PwrTest
        sleep/wake cycle (step 06) produces a clean, uncontaminated report,
        then reboot so that PwrTest runs on a fresh system state.

        After reboot, pytest resumes at test_06_pwrtest_sleep_wake.
        """
        logger.info("[TEST_05] Clearing Sleep Study history")
        try:
            cleaner = SleepHistoryCleaner()
            deleted = cleaner.clear()
            logger.info(f"[TEST_05] SleepHistory cleared: {deleted} file(s) deleted")
        except Exception as exc:
            logger.warning(f"[TEST_05] SleepHistory clear failed (non-fatal): {exc}")

        # Pre-mark this test completed BEFORE os._exit(0) inside setup_reboot.
        self.reboot_mgr.pre_mark_completed(request.node.name)

        self.reboot_mgr.setup_reboot(
            delay=10,
            reason="STC-2562 Phase A complete — rebooting before PwrTest sleep/wake cycle",
            test_file=__file__,
        )
        # os._exit(0) is called inside setup_reboot — code below never executes

    @pytest.mark.order(6)
    # @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")
    @step(6, "PwrTest — sleep/wake cycle + collect sleepstudy")
    def test_06_pwrtest_sleep_wake(self):
        """
        Record pre-sleep timestamp, run one sleep/wake cycle via PwrTestController,
        then generate a sleepstudy HTML report via SleepStudyController.
        """
        logger.info("[TEST_06] PwrTest sleep/wake started")

        # Record time before sleep for sleepstudy filtering
        TestSTC2562ModernStandby._pre_sleep_time = datetime.now().isoformat(timespec='seconds')
        logger.info(f"[TEST_06] pre_sleep_time: {self._pre_sleep_time}")

        cfg = self.config['pwrtest']
        pwrtest = PwrTestController(
            pwrtest_base_dir=cfg['pwrtest_base_dir'],
            os_name=cfg.get('os_name', 'win11'),
            os_version=cfg.get('os_version', '24H2'),
            scenario=PwrTestScenario.CS,  # Connected Standby (S0ix / Modern Standby)
            cycle_count=1,
            delay_seconds=10,
            wake_after_seconds=60*15,  # 15 minutes — long enough to trigger deep S0ix states
            timeout_seconds=300,
            log_path=cfg['log_path'],
        )
        pwrtest.start()
        pwrtest.join(timeout=cfg.get('timeout', 300))

        if not pwrtest.status:
            pytest.fail(f"PwrTest failed: {pwrtest.result_summary}")

        TestSTC2562ModernStandby._post_sleep_time = datetime.now().isoformat(timespec='seconds')
        logger.info(f"[TEST_06] post_sleep_time: {self._post_sleep_time}")

        # Generate sleepstudy report immediately after waking
        ss_cfg = self.config['sleepstudy']
        ss_ctrl = SleepStudyController(
            output_path=ss_cfg['output_path'],
            timeout=ss_cfg.get('timeout', 60),
        )
        ss_ctrl.start()
        ss_ctrl.join()

        if not ss_ctrl.status:
            pytest.fail(f"SleepStudy generation failed: {ss_ctrl.error_message}")

        # Cache controller on class for step 07
        TestSTC2562ModernStandby._sleepstudy_ctrl = ss_ctrl
        logger.info("[TEST_06] PwrTest + sleepstudy complete")

    @pytest.mark.order(7)
    # @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")
    @step(7, "Verify sleepstudy SW/HW DRIPS >= 90%")
    def test_07_verify_sleepstudy(self):
        """
        Parse sleepstudy-report.html for sleep sessions that occurred during
        the PwrTest window and verify SW DRIPS ≥ 90% and HW DRIPS ≥ 90%.

        High DRIPS (% of time in low-power state) indicates the SSD correctly
        entered low-power mode during sleep.
        """
        logger.info("[TEST_07] Sleepstudy verification started")

        ss_cfg = self.config['sleepstudy']
        # threshold = ss_cfg.get('sw_hw_threshold_pct', 90)
        report_path = ss_cfg['output_path']
        threshold = 90

        assert Path(report_path).exists(), f"Sleepstudy report not found: {report_path}"

        parser = SleepReportParser(report_path)
        sessions = parser.get_sleep_sessions(
            start_dt=self._pre_sleep_time,
            end_dt=self._post_sleep_time,
        )

        assert len(sessions) > 0, (
            f"No sleep sessions found in {report_path} between "
            f"{self._pre_sleep_time} and {self._post_sleep_time}"
        )

        logger.info(f"[TEST_07] Found {len(sessions)} sleep session(s) in window")
        failures = []
        for s in sessions:
            sw = s.sw_pct
            hw = s.hw_pct
            logger.info(f"[TEST_07]   Session {s.session_id}: SW={sw}%  HW={hw}%")

            # SW and HW values must be present
            if sw is None:
                failures.append(f"Session {s.session_id}: SW DRIPS not found (None)")
            elif sw < threshold:
                failures.append(f"Session {s.session_id}: SW DRIPS {sw}% < {threshold}%")

            if hw is None:
                failures.append(f"Session {s.session_id}: HW DRIPS not found (None)")
            elif hw < threshold:
                failures.append(f"Session {s.session_id}: HW DRIPS {hw}% < {threshold}%")

        if failures:
            pytest.fail("Sleepstudy DRIPS validation failed:\n" + "\n".join(failures))

        logger.info("[TEST_07] All sleep sessions passed SW/HW check")

    @pytest.mark.order(8)
    @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")    
    @step(8, "OsConfig — apply OS settings")
    def test_08_apply_osconfig(self):
        """
        Apply OS configuration for clean Modern Standby testing:
        - Disable Windows Search Index
        - Disable OneDrive (including file-storage prevention)
        - Disable Windows Defender real-time protection
        """
        logger.info("[TEST_08] OsConfig apply started")

        cfg = self.config.get('osconfig', {})
        profile = OsConfigProfile(
            disable_search_index=cfg.get('disable_search_index', False),
            disable_onedrive=cfg.get('disable_onedrive', False),
            disable_defender=cfg.get('disable_defender', False),
        )

        controller = OsConfigController(profile=profile)
        controller.apply_all()

        # Cache for potential teardown revert (best-effort)
        TestSTC2562ModernStandby._osconfig_controller = controller

        logger.info("[TEST_08] OsConfig applied successfully")

    @pytest.mark.order(9)
    @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")
    @step(9, "Clear Sleep Study history & Reboot device")
    def test_09_clear_sleepstudy_and_reboot(self, request):
        """
        Schedule a system reboot.  After reboot, pytest is re-invoked automatically
        via the Windows Startup folder BAT created by RebootManager.  The
        completed_tests list in the state file ensures steps 01–08 are skipped on
        resume and this step is not re-executed (no infinite reboot loop).
        """
        logger.info("[TEST_09] Scheduling reboot")

        # ── Clear accumulated Sleep Study history ─────────────────────────────
        try:
            cleaner = SleepHistoryCleaner()
            deleted = cleaner.clear()
            logger.info(f"[TEST_09] SleepHistory cleared: {deleted} file(s) deleted")
        except Exception as exc:
            logger.warning(f"[TEST_09] SleepHistory clear failed (non-fatal): {exc}")

        # Pre-mark this test as completed BEFORE setup_reboot() calls os._exit(0).
        # Without this, test_08 would not be in completed_tests after reboot
        # and would execute again → infinite reboot loop.
        self.reboot_mgr.pre_mark_completed(request.node.name)

        self.reboot_mgr.setup_reboot(
            delay=10,
            reason="STC-2562 Phase A complete — rebooting for Modern Standby test",
            test_file=__file__,
        )
        # os._exit(0) is called inside setup_reboot — code below never executes

    # ------------------------------------------------------------------
    # Phase B — Post-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(10)
    @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")
    @step(10, "PHM collector — run Modern Standby")
    def test_10_run_modern_standby(self):
        """
        Post-reboot: launch PHM, open the web UI, configure and run the Modern
        Standby Cycling collector scenario using parameters from Config.json,
        wait for completion, then copy the trace folder to testlog/PHMTraces/.
        """
        self.reboot_mgr.require_rebooted(min_count=2)
        logger.info("[TEST_10] PHM collector session started")


        # ── Verify PHM is installed ───────────────────────────────────
        phm_cfg = self.config['phm']
        mgr = PHMProcessManager(install_path=phm_cfg['install_path'])
        if not mgr.is_installed():
            pytest.fail(
                "PHM is not installed — cannot launch collector. "
                "Ensure test_03 ran successfully before this reboot."
            )

        # ── Launch PHM process ────────────────────────────────────────
        mgr.launch()
        logger.info("[TEST_10] PHM process launched")

        # ── Read collector parameters from Config ─────────────────────
        col_cfg = self.config.get('phm_collector', {})
        cycle_count               = col_cfg.get('cycle_count', 1)
        delayed_start_seconds     = col_cfg.get('delayed_start_seconds', 10)
        scenario_duration_minutes = col_cfg.get('scenario_duration_minutes', 15)
        wait_for_server_seconds   = col_cfg.get('wait_for_server_seconds', 60)
        completion_timeout        = col_cfg.get('completion_timeout_seconds', 7200)
        headless                  = col_cfg.get('headless', True)
        traces_output_dir         = col_cfg.get('traces_output_dir', './testlog/PHMTraces')

        params = ModernStandbyCyclingParams(
            delayed_start_seconds=delayed_start_seconds,
            scenario_duration_minutes=scenario_duration_minutes,
            cycle_count=cycle_count,
        )
        logger.info(
            f"[TEST_10] Collector params: cycles={cycle_count}, "
            f"delayed_start={delayed_start_seconds}s, "
            f"duration={scenario_duration_minutes}min"
        )

        # ── Open PHM web UI via Playwright ────────────────────────────
        ui = PHMUIMonitor(host='localhost', port=1337, headless=headless)
        try:
            logger.info(f"[TEST_10] Waiting for PHM server (timeout={wait_for_server_seconds}s)")
            ui.wait_for_ready(timeout=wait_for_server_seconds)
            logger.info("[TEST_10] PHM server ready — opening browser")
            # ui.open_browser(headless=headless)
            ui.open_browser(headless=False)

            # ── Run the collector session (steps 3-9 via CollectorSession) ──
            TestSTC2562ModernStandby._phm_start_time = datetime.now().isoformat(timespec='seconds')
            session = CollectorSession(ui)
            session.run(params)
            logger.info("[TEST_10] CollectorSession.run() finished — test is running")

            # ── Poll for completion ───────────────────────────────────
            logger.info(f"[TEST_10] Waiting for completion (timeout={completion_timeout}s)")
            completed = ui.wait_for_completion(timeout=completion_timeout)
            if not completed:
                pytest.fail("PHM collector did not complete within the configured timeout")
            TestSTC2562ModernStandby._phm_end_time = datetime.now().isoformat(timespec='seconds')
            logger.info("[TEST_10] PHM collector completed")

            # ── Collect traces ────────────────────────────────────────
            try:
                traces_src = ui.get_traces_path()
                dest_dir = Path(traces_output_dir)
                if dest_dir.exists():
                    shutil.rmtree(str(dest_dir))
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(traces_src, str(dest_dir), dirs_exist_ok=True)
                logger.info(f"[TEST_10] Traces copied: {traces_src} -> {dest_dir}")
            except Exception as exc:
                logger.warning(f"[TEST_10] Trace collection failed (non-fatal): {exc}")

        finally:
            try:
                ui.close_browser()
                logger.info("[TEST_10] Browser closed")
            except Exception as exc:
                logger.warning(f"[TEST_10] close_browser error (non-fatal): {exc}")

    @pytest.mark.order(11)
    @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")
    @step(11, "Verify DRIPS — SW/HW > 80%")
    def test_11_verify_drips(self):
        """
        Generate a Sleep Study report covering the PHM collection window
        (phm_start_time ... phm_end_time captured in test_10), then verify
        that every session's SW DRIPS and HW DRIPS are both > 80%.
        """
        # self._skip_if_not_rebooted()
        logger.info("[TEST_11] Sleep Study DRIPS verification started")

        # Require that test_10 actually ran and captured timestamps
        if not self._phm_start_time or not self._phm_end_time:
            pytest.fail(
                "PHM timestamps not set — test_10 must complete successfully "
                "before this step can run"
            )

        # ── Generate Sleep Study report ───────────────────────────────
        ss_cfg = self.config['sleepstudy']
        ss_ctrl = SleepStudyController(
            output_path=ss_cfg['output_path'],
            timeout=ss_cfg.get('timeout', 60),
        )
        ss_ctrl.start()
        ss_ctrl.join()
        if not ss_ctrl.status:
            pytest.fail(f"SleepStudy report generation failed: {ss_ctrl.error_message}")
        logger.info(f"[TEST_11] Sleep Study report generated: {ss_cfg['output_path']}")

        # ── Parse SW/HW DRIPS and verify ─────────────────────────────
        drips_threshold = 80
        report_path = ss_cfg['output_path']
        assert Path(report_path).exists(), f"Sleep Study report not found: {report_path}"

        parser = SleepReportParser(report_path)
        sessions = parser.get_sleep_sessions(
            start_dt=self._phm_start_time,
            end_dt=self._phm_end_time,
        )
        if not sessions:
            pytest.fail(
                f"No sleep sessions found in report between "
                f"{self._phm_start_time} and {self._phm_end_time}"
            )
        logger.info(f"[TEST_11] Found {len(sessions)} sleep session(s)")

        failures = []
        for s in sessions:
            sw, hw = s.sw_pct, s.hw_pct
            logger.info(f"[TEST_11]   Session {s.session_id}: SW={sw}%  HW={hw}%")
            if sw is None:
                failures.append(f"Session {s.session_id}: SW DRIPS not found")
            elif sw <= drips_threshold:
                failures.append(f"Session {s.session_id}: SW DRIPS {sw}% ≤ {drips_threshold}%")
            if hw is None:
                failures.append(f"Session {s.session_id}: HW DRIPS not found")
            elif hw <= drips_threshold:
                failures.append(f"Session {s.session_id}: HW DRIPS {hw}% ≤ {drips_threshold}%")

        if failures:
            pytest.fail("Sleep Study DRIPS check failed:\n" + "\n".join(failures))
        logger.info("[TEST_11] Sleep Study DRIPS check passed")

    @pytest.mark.order(12)
    @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")
    @step(12, "CDI After — SMART snapshot")
    def test_12_cdi_after(self):
        """Run CrystalDiskInfo to capture post-test SMART data (After_ prefix)."""
        self._skip_if_not_rebooted()
        logger.info("[TEST_12] CDI After started")

        cfg = self.config['cdi']
        ctrl = CDIController(
            executable_path=cfg['ExePath'],
            log_path=cfg['LogPath'],
            log_prefix='After_',
            screenshot_drive_letter=cfg.get('ScreenShotDriveLetter', 'C:'),
        )
        ctrl.start()
        ctrl.join(timeout=180)

        if not ctrl.status:
            pytest.fail(f"CDI After failed (status={ctrl.status})")

        logger.info("[TEST_12] CDI After complete")

    @pytest.mark.order(13)
    @pytest.mark.skip(reason="Dependent on PHM, which is currently blocked — will re-enable once PHM is testable")    
    @step(13, "SMART compare — verify drive health")
    def test_13_smart_compare(self):
        """
        Compare Before_ and After_ SMART snapshots:
        - Unsafe Shutdowns must NOT increase (indicates clean shutdown path)
        - Reallocated Sectors Count, Current Pending Sector Count,
          Uncorrectable Sector Count must all be 0
        """
        self._skip_if_not_rebooted()
        logger.info("[TEST_13] SMART comparison started")

        cdi_cfg = self.config['cdi']
        smart_cfg = self.config['smart_check']
        drive = smart_cfg.get('drive_letter', cdi_cfg.get('ScreenShotDriveLetter', 'C:'))

        ctrl = CDIController(
            executable_path=cdi_cfg['ExePath'],
            log_path=cdi_cfg['LogPath'],
        )

        # ── Check: Unsafe Shutdowns must not increase ──────────────────
        no_increase_attrs = smart_cfg.get('no_increase_attributes', ['Unsafe Shutdowns'])
        ok, msg = ctrl.compare_smart_value_no_increase(
            drive_letter=drive,
            before_prefix='Before_',
            after_prefix='After_',
            keys=no_increase_attrs,
        )
        if not ok:
            pytest.fail(f"SMART no-increase check failed: {msg}")
        logger.info(f"[TEST_13] No-increase check passed: {no_increase_attrs}")

        # ── Check: error counters must be 0 ───────────────────────────
        zero_attrs = smart_cfg.get('must_be_zero_attributes', [])
        for attr in zero_attrs:
            ok, msg = ctrl.compare_smart_value(
                drive_letter=drive,
                log_prefix='After_',
                keys=[attr],
                expected_value=0,
            )
            if not ok:
                pytest.fail(f"SMART zero-check failed: {msg}")
            logger.info(f"[TEST_13] Zero-check passed: {attr}")

        logger.info("[TEST_13] All SMART checks passed")
