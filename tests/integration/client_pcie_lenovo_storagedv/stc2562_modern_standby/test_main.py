"""
STC-2562: Modern Standby Integration Test

Tests SSD health and compatibility under Windows Modern Standby (ACPI S0ix)
using the PHM (Powerhouse Mountain) toolchain.

Test Flow:
    Phase A — Pre-Reboot:
    1. Precondition  — create log directories
    2. CDI Before    — SMART baseline
    3. Install PHM   — silent installer
    4. PEPChecker    — run NDA collector, collect logs
    5. PwrTest       — sleep/wake cycle + collect sleepstudy
    6. Verify sleep  — SW/HW DRIPS ≥ 90 %
    7. OsConfig      — apply OS settings
    8. Reboot        — schedule reboot, terminate session

    Phase B — Post-Reboot:
    9.  PHM web      — launch PHM and verify web UI is responsive
    10. CDI After    — SMART snapshot
    11. SMART check  — Unsafe Shutdowns unchanged; error counters == 0
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
from lib.testtool.phm.exceptions import PHMInstallError
from lib.testtool.pwrtest import PwrTestController
from lib.testtool.sleepstudy import SleepStudyController
from lib.testtool.sleepstudy.sleep_report_parser import SleepReportParser
from lib.testtool.osconfig import OsConfigController
from lib.testtool.osconfig.config import OsConfigProfile
from lib.testtool.reboot import OsRebootController, OsRebootStateManager
from lib.logger import get_module_logger, logConfig

logger = get_module_logger(__name__)

# ---------------------------------------------------------------------------
# Phase detection helpers
# ---------------------------------------------------------------------------

_STATE_FILE_REL = './testlog/reboot_state.json'


def _is_recovering() -> bool:
    """Return True when running in the post-reboot (recovery) phase."""
    mgr = OsRebootStateManager(_STATE_FILE_REL)
    return mgr.is_recovering()


def _skip_if_recovering(reason: str = "Pre-reboot step — skip after reboot"):
    """pytest.skip when we are in the post-reboot phase."""
    if _is_recovering():
        pytest.skip(reason)


def _skip_if_not_recovering(reason: str = "Post-reboot step — skip before reboot"):
    """pytest.skip when we are NOT in the post-reboot phase."""
    if not _is_recovering():
        pytest.skip(reason)


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
            mgr.kill_by_name('PHM.exe')
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

    def _cleanup_test_logs(self) -> None:
        """
        Remove leftover logs from previous test runs.

        Cleans:
        1. CDI logs  (testlog/CDILog/)
        2. SleepStudy report  (testlog/sleepstudy-report.html)
        3. PEPChecker logs  (testlog/PEPChecker_Log/)
        4. PwrTest logs  (testlog/PwrTestLog/)
        5. Test-specific log directory  (log/STC-2562/)
        """
        logger.info("[_cleanup_test_logs] Starting test log cleanup")

        # Ensure base testlog dir exists before any cleanup attempts
        Path('./testlog').mkdir(parents=True, exist_ok=True)

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

        phase = "POST-REBOOT (recovery)" if _is_recovering() else "PRE-REBOOT"
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

        logger.info("STC-2562 session complete")
        os.chdir(cls.original_cwd)

    # ------------------------------------------------------------------
    # Phase A — Pre-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition — cleanup and create log directories")
    def test_01_precondition(self):
        """
        Precondition setup:
        1. Remove existing PHM installation (clean slate)
        2. Clean up leftover logs from previous runs
        3. Create fresh log directory structure
        """
        _skip_if_recovering()
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
    @step(2, "CDI Before — SMART baseline")
    def test_02_cdi_before(self):
        """Run CrystalDiskInfo to capture SMART baseline (Before_ prefix)."""
        _skip_if_recovering()
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
    @step(3, "Install PHM tool")
    def test_03_install_phm(self):
        """Install Powerhouse Mountain (PHM) tool silently."""
        _skip_if_recovering()
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
    @step(4, "PEPChecker — run NDA collector")
    def test_04_run_pep_checker(self):
        """
        Execute PEPChecker.exe, verify 4 output files, and collect them into
        testlog/PEPChecker_Log/.

        Output files: PBC-Report.html, PBC-sleepstudy-report.html,
                      PBC-Debug-Log.txt, PBC-Errors.txt
        """
        _skip_if_recovering()
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
    @step(5, "PwrTest — sleep/wake cycle + collect sleepstudy")
    def test_05_pwrtest_sleep_wake(self):
        """
        Record pre-sleep timestamp, run one sleep/wake cycle via PwrTestController,
        then generate a sleepstudy HTML report via SleepStudyController.
        """
        _skip_if_recovering()
        logger.info("[TEST_05] PwrTest sleep/wake started")

        # Record time before sleep for sleepstudy filtering
        TestSTC2562ModernStandby._pre_sleep_time = datetime.now().isoformat()
        logger.info(f"[TEST_05] pre_sleep_time: {self._pre_sleep_time}")

        cfg = self.config['pwrtest']
        pwrtest = PwrTestController(
            pwrtest_base_dir=cfg['pwrtest_base_dir'],
            os_name=cfg.get('os_name', 'win11'),
            os_version=cfg.get('os_version', '24H2'),
            cycle_count=cfg.get('cycle_count', 1),
            delay_seconds=cfg.get('delay_seconds', 10),
            wake_after_seconds=cfg.get('wake_after_seconds', 60),
            log_path=cfg['log_path'],
        )
        pwrtest.start()
        pwrtest.join(timeout=cfg.get('timeout', 300))

        if not pwrtest.status:
            pytest.fail(f"PwrTest failed: {pwrtest.result_summary}")

        TestSTC2562ModernStandby._post_sleep_time = datetime.now().isoformat()
        logger.info(f"[TEST_05] post_sleep_time: {self._post_sleep_time}")

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

        # Cache controller on class for step 06
        TestSTC2562ModernStandby._sleepstudy_ctrl = ss_ctrl
        logger.info("[TEST_05] PwrTest + sleepstudy complete")

    @pytest.mark.order(6)
    @step(6, "Verify sleepstudy SW/HW DRIPS ≥ 90%")
    def test_06_verify_sleepstudy(self):
        """
        Parse sleepstudy-report.html for sleep sessions that occurred during
        the PwrTest window and verify SW DRIPS ≥ 90% and HW DRIPS ≥ 90%.

        High DRIPS (% of time in low-power state) indicates the SSD correctly
        entered low-power mode during sleep.
        """
        _skip_if_recovering()
        logger.info("[TEST_06] Sleepstudy verification started")

        ss_cfg = self.config['sleepstudy']
        threshold = ss_cfg.get('sw_hw_threshold_pct', 90)
        report_path = ss_cfg['output_path']

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

        logger.info(f"[TEST_06] Found {len(sessions)} sleep session(s) in window")
        failures = []
        for s in sessions:
            sw = s.sw_pct
            hw = s.hw_pct
            logger.info(f"[TEST_06]   Session {s.session_id}: SW={sw}%  HW={hw}%")

            if sw is not None and sw < threshold:
                failures.append(f"Session {s.session_id}: SW DRIPS {sw}% < {threshold}%")
            if hw is not None and hw < threshold:
                failures.append(f"Session {s.session_id}: HW DRIPS {hw}% < {threshold}%")

        if failures:
            pytest.fail("Sleepstudy DRIPS below threshold:\n" + "\n".join(failures))

        logger.info("[TEST_06] All sleep sessions passed SW/HW check")

    @pytest.mark.order(7)
    @step(7, "OsConfig — apply OS settings")
    def test_07_apply_osconfig(self):
        """
        Apply OS configuration for clean Modern Standby testing:
        - Disable Windows Search Index
        - Disable OneDrive (including file-storage prevention)
        - Disable Windows Defender real-time protection
        """
        _skip_if_recovering()
        logger.info("[TEST_07] OsConfig apply started")

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

        logger.info("[TEST_07] OsConfig applied successfully")

    @pytest.mark.order(8)
    @step(8, "Reboot device")
    def test_08_reboot(self):
        """
        Schedule a system reboot.  After reboot, pytest is re-invoked by the
        run_test framework; the OsRebootStateManager state file flags the
        post-reboot (recovery) phase so steps 01–08 are automatically skipped.
        """
        _skip_if_recovering()
        logger.info("[TEST_08] Scheduling reboot")

        cfg = self.config['reboot']
        ctrl = OsRebootController(
            delay_seconds=cfg.get('delay_seconds', 10),
            reboot_count=1,
            state_file=cfg.get('state_file', _STATE_FILE_REL),
        )
        ctrl.start()
        ctrl.join(timeout=60)

        logger.info("[TEST_08] Reboot scheduled — system will restart shortly")

    # ------------------------------------------------------------------
    # Phase B — Post-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(9)
    @step(9, "Open PHM web UI (post-reboot)")
    def test_09_open_phm_web(self):
        """
        Launch PHM and verify the Node.js web UI is reachable at
        http://localhost:1337 within 60 seconds.
        """
        _skip_if_not_recovering()
        logger.info("[TEST_09] PHM web launch started")

        cfg = self.config['phm']
        mgr = PHMProcessManager(install_path=cfg['install_path'])

        if not mgr.is_installed():
            pytest.fail(
                "PHM is not installed — cannot launch web UI. "
                "Ensure test_03 ran successfully before this reboot."
            )

        mgr.launch()
        logger.info("[TEST_09] PHM process launched — polling http://localhost:1337")

        # Poll until the web UI responds or timeout
        deadline = time.time() + 60
        last_exc = None
        while time.time() < deadline:
            try:
                urllib.request.urlopen('http://localhost:1337', timeout=5)
                logger.info("[TEST_09] PHM web UI is responsive")
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(3)

        pytest.fail(f"PHM web UI did not become available within 60 s: {last_exc}")

    @pytest.mark.order(10)
    @step(10, "CDI After — SMART snapshot")
    def test_10_cdi_after(self):
        """Run CrystalDiskInfo to capture post-test SMART data (After_ prefix)."""
        _skip_if_not_recovering()
        logger.info("[TEST_10] CDI After started")

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

        logger.info("[TEST_10] CDI After complete")

    @pytest.mark.order(11)
    @step(11, "SMART compare — verify drive health")
    def test_11_smart_compare(self):
        """
        Compare Before_ and After_ SMART snapshots:
        - Unsafe Shutdowns must NOT increase (indicates clean shutdown path)
        - Reallocated Sectors Count, Current Pending Sector Count,
          Uncorrectable Sector Count must all be 0
        """
        _skip_if_not_recovering()
        logger.info("[TEST_11] SMART comparison started")

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
        logger.info(f"[TEST_11] No-increase check passed: {no_increase_attrs}")

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
            logger.info(f"[TEST_11] Zero-check passed: {attr}")

        logger.info("[TEST_11] All SMART checks passed")
