"""
STC-547: Modern Standby Integration Test (Intel RVP)

Tests SSD Modern Standby compatibility using the PHM (Powerhouse Mountain)
toolchain on an Intel RVP platform.

Test Flow:
    Phase A — Pre-Reboot:
    1. Precondition  — create log directories
    2. Install PHM   — silent installer
    3. OsConfig      — apply OS settings
    4. Clear Sleep Study history & Reboot — clean slate before PHM collector

    Phase B — Post-Reboot:
    5. PHM collector — run Modern Standby Cycling scenario
    6. Verify DRIPS  — generate sleepstudy report; SW/HW DRIPS > 80%
    7. PHM Visualizer — PCIe LPM check; L1.2 >= threshold
    8. PHM Visualizer — PCIe LTR check; Min <= 50 ms
    9. PHM Visualizer — OS Events / Modern Standby; Entered >= 90%
"""

import sys
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
# tests/integration/test_case/stc547_intel_rvp_modern_standby/test_main.py
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.test_utils import cleanup_directory
from lib.testtool.phm import PHMController
from lib.testtool.phm.process_manager import PHMProcessManager
from lib.testtool.phm.ui_monitor import PHMUIMonitor
from lib.testtool.phm.collector_session import CollectorSession
from lib.testtool.browser_setup import ensure_playwright_chromium
from lib.testtool.phm.scenarios.modern_standby_cycling import ModernStandbyCyclingParams
from lib.testtool.phm.visualizer import VisualizerConfig, run_visualizer_check
from lib.testtool.sleepstudy import SleepStudyController
from lib.testtool.sleepstudy.sleep_report_parser import SleepReportParser, validate_drips
from lib.testtool.sleepstudy.history_cleaner import SleepHistoryCleaner
from lib.testtool.osconfig import OsConfigController
from lib.testtool.osconfig.config import OsConfigProfile
from lib.testtool.osconfig.state_manager import OsConfigStateManager
from lib.logger import get_module_logger, clear_log_files
from framework.reboot_manager import RebootManager

logger = get_module_logger(__name__)

# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.client_intel_rvp
@pytest.mark.interface_pcie
@pytest.mark.feature_modern_standby
@pytest.mark.slow
class TestSTC547IntelRVPModernStandby(BaseTestCase):
    """
    STC-547: Modern Standby Test for Intel RVP (PCIe)
    """

    # Class-level state shared between steps
    _phm_start_time: str = ""
    _phm_end_time: str = ""
    _osconfig_controller: "OsConfigController | None" = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _remove_existing_phm(self) -> bool:
        """Ensure PHM is fully removed before a fresh install (delegates to PHMController.force_remove)."""
        phm_cfg = self.config['phm']
        ctrl = PHMController(
            installer_path=phm_cfg['installer'],
            install_path=phm_cfg['install_path'],
        )
        return ctrl.force_remove()

    def _cleanup_test_logs(self) -> None:
        """
        Remove leftover logs from previous test runs.

        Cleans:
        1. SleepStudy report  (testlog/sleepstudy-report.html)
        2. PHM traces         (testlog/PHMTraces/)
        3. Test-specific log files  (log/STC-547/log.txt, log.err, ...)
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

        # 1. SleepStudy HTML report
        ss_cfg = self.config.get('sleepstudy', {})
        ss_report = Path(ss_cfg.get('output_path', './testlog/sleepstudy-report.html'))
        if ss_report.exists():
            ss_report.unlink()
            logger.info(f"[_cleanup_test_logs] Removed sleepstudy report: {ss_report}")
        else:
            logger.info(f"[_cleanup_test_logs] No sleepstudy report to remove: {ss_report}")

        # 2. PHM traces
        cleanup_directory('./testlog/PHMTraces', 'PHM traces directory', logger)

        # 3. Test-specific log directory
        log_path = self.config.get('log_path', './log/STC-547')
        cleanup_directory(log_path, 'test log directory', logger)

        # 3a. Clear the logger's own log files (lib/logger.py writes to ./log/log.txt
        #     and ./log/log.err, separate from the test-specific log_path above).
        clear_log_files()
        logger.info("[_cleanup_test_logs] Logger log files cleared")

        logger.info("[_cleanup_test_logs] Cleanup complete")

    # ------------------------------------------------------------------
    # Fixture
    # ------------------------------------------------------------------

    @pytest.fixture(scope="class", autouse=True)
    def setup_test_class(self, request, testcase_config, runcard_params):
        """Load configuration and initialize test class (runs before all tests)."""
        cls = request.cls
        cls.original_cwd = os.getcwd()

        # ── Working directory + logging ────────────────────────────────────────
        test_dir = cls._setup_working_directory(__file__)

        # ── Config ────────────────────────────────────────────────────────────
        cls.config = testcase_config.tool_config
        cls.bin_path = testcase_config.bin_directory

        # ── RebootManager (must be after os.chdir) ────────────────────────────
        cls.reboot_mgr = RebootManager(total_tests=cls._count_test_methods())

        phase = "POST-REBOOT (recovering)" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
        logger.info(f"[SETUP] Phase: {phase}")
        logger.info(f"[SETUP] Test case: {testcase_config.case_id}  version: {testcase_config.case_version}")
        logger.info(f"[SETUP] Working directory: {test_dir}")

        # ── RunCard ───────────────────────────────────────────────────────────
        cls._init_runcard(runcard_params)

        yield

        # ── Teardown ──────────────────────────────────────────────────────────
        cls._teardown_runcard(request.session)

        # Revert OS configuration changes applied in test_03 (best-effort, STC-547 specific)
        if cls._osconfig_controller is not None:
            # Pre-Reboot path: controller is still alive in-process
            try:
                logger.info("[TEARDOWN] Reverting OsConfig changes (pre-reboot path)...")
                cls._osconfig_controller.revert_all()
                logger.info("[TEARDOWN] OsConfig reverted successfully")
            except Exception as exc:
                logger.warning(f"[TEARDOWN] OsConfig revert failed — {exc} (continuing)")
        else:
            # Post-Reboot path: _osconfig_controller was lost across the reboot;
            # reconstruct the controller from config so revert_all() can load
            # the snapshot that was persisted to disk before the reboot.
            state_mgr = OsConfigStateManager()
            if state_mgr.exists():
                try:
                    logger.info("[TEARDOWN] Post-reboot OsConfig revert — loading snapshot from disk")
                    cfg = cls.config.get('osconfig', {})
                    profile = OsConfigProfile(
                        disable_search_index=cfg.get('disable_search_index', False),
                        disable_onedrive=cfg.get('disable_onedrive', False),
                        disable_onedrive_tasks=cfg.get('disable_onedrive_tasks', False),
                        disable_edge_update_tasks=cfg.get('disable_edge_update_tasks', False),
                        disable_defender=cfg.get('disable_defender', False),
                    )
                    controller = OsConfigController(
                        profile=profile,
                        state_manager=state_mgr,
                    )
                    controller.revert_all()
                    logger.info("[TEARDOWN] OsConfig reverted successfully (post-reboot)")
                except Exception as exc:
                    logger.warning(f"[TEARDOWN] OsConfig post-reboot revert failed — {exc} (continuing)")
            else:
                logger.info("[TEARDOWN] No OsConfig snapshot on disk — skipping revert")

        cls._teardown_reboot_manager()

        logger.info(f"{cls.__name__} session complete")
        os.chdir(cls.original_cwd)

    # ------------------------------------------------------------------
    # Phase A — Pre-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition — cleanup and create log directories")
    def test_01_precondition(self):
        """
        Precondition setup:
        1. Clean up leftover logs from previous runs
        2. Remove existing PHM installation (clean slate)
        3. Create fresh log directory structure
        4. Ensure Playwright Chromium is installed
        """
        logger.info("[TEST_01] Precondition setup started")

        # Step 1: Clean up logs from previous runs
        self._cleanup_test_logs()

        # Step 2: Remove existing PHM installation
        if not self._remove_existing_phm():
            pytest.fail("Failed to remove existing PHM installation")

        # Step 3: Re-create fresh log directories
        for d in [
            './testlog',
            './testlog/PHMTraces',
            self.config.get('log_path', './log/STC-547'),
        ]:
            Path(d).mkdir(parents=True, exist_ok=True)
            logger.info(f"[TEST_01] Directory ready: {d}")

        # Step 4: Ensure playwright Chromium browser binary is installed.
        ensure_playwright_chromium(logger)

        logger.info("[TEST_01] Precondition complete")

    @pytest.mark.order(2)
    @step(2, "Install PHM tool")
    def test_02_install_phm(self):
        """Install Powerhouse Mountain (PHM) tool silently."""
        logger.info("[TEST_02] PHM install started")

        cfg = self.config['phm']
        ctrl = PHMController(
            installer_path=cfg['installer'],
            install_path=cfg['install_path'],
        )

        if ctrl.is_installed():
            logger.info("[TEST_02] PHM already installed — skip install step")
        else:
            ctrl.install()

        assert ctrl.is_installed(), "PHM installation not detected after install"
        logger.info("[TEST_02] PHM install complete")

    @pytest.mark.order(3)
    @step(3, "OsConfig — apply OS settings")
    def test_03_apply_osconfig(self):
        """
        Apply OS configuration for clean Modern Standby testing:
        - Disable Windows Search Index
        - Disable OneDrive (including file-storage prevention)
        - Disable Windows Defender real-time protection
        """
        logger.info("[TEST_03] OsConfig apply started")

        cfg = self.config.get('osconfig', {})
        profile = OsConfigProfile(
            disable_search_index=cfg.get('disable_search_index', False),
            disable_onedrive=cfg.get('disable_onedrive', False),
            disable_onedrive_tasks=cfg.get('disable_onedrive_tasks', False),
            disable_edge_update_tasks=cfg.get('disable_edge_update_tasks', False),
            disable_defender=cfg.get('disable_defender', False),
        )

        controller = OsConfigController(
            profile=profile,
            state_manager=OsConfigStateManager(),
        )
        controller.apply_all()

        # Cache for potential teardown revert (best-effort)
        TestSTC547IntelRVPModernStandby._osconfig_controller = controller

        logger.info("[TEST_03] OsConfig applied successfully")

    @pytest.mark.order(4)
    @step(4, "Clear Sleep Study history & Reboot device")
    def test_04_clear_sleepstudy_and_reboot(self, request):
        """
        Clear accumulated Sleep Study history so that the subsequent PHM
        Modern Standby Cycling scenario (step 05) produces a clean,
        uncontaminated report, then reboot so that PHM runs on a fresh
        system state.

        After reboot, pytest resumes at test_05_run_modern_standby.
        """
        logger.info("[TEST_04] Clearing Sleep Study history")
        try:
            cleaner = SleepHistoryCleaner()
            deleted = cleaner.clear()
            logger.info(f"[TEST_04] SleepHistory cleared: {deleted} file(s) deleted")
        except Exception as exc:
            logger.warning(f"[TEST_04] SleepHistory clear failed (non-fatal): {exc}")

        # Pre-mark this test completed BEFORE os._exit(0) inside setup_reboot.
        self.reboot_mgr.pre_mark_completed(request.node.name)

        self.reboot_mgr.setup_reboot(
            delay=10,
            reason="STC-547 Phase A complete — rebooting before PHM Modern Standby collector",
            test_file=__file__,
        )
        # os._exit(0) is called inside setup_reboot — code below never executes

    # ------------------------------------------------------------------
    # Phase B — Post-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(5)
    @step(5, "PHM collector — run Modern Standby")
    def test_05_run_modern_standby(self):
        """
        Post-reboot: launch PHM, open the web UI, configure and run the Modern
        Standby Cycling collector scenario using parameters from Config.json,
        wait for completion, then copy the trace folder to testlog/PHMTraces/.
        """
        self.reboot_mgr.require_after("test_04_clear_sleepstudy_and_reboot")
        logger.info("[TEST_05] PHM collector session started")

        # ── Verify PHM is installed ───────────────────────────────────
        phm_cfg = self.config['phm']
        mgr = PHMProcessManager(install_path=phm_cfg['install_path'])
        if not mgr.is_installed():
            pytest.fail(
                "PHM is not installed — cannot launch collector. "
                "Ensure test_02 ran successfully before this reboot."
            )

        # ── Launch PHM process ────────────────────────────────────────
        mgr.launch()
        logger.info("[TEST_05] PHM process launched")

        # ── Read collector parameters from Config ─────────────────────
        col_cfg = self.config.get('phm_collector', {})
        cycle_count               = col_cfg.get('cycle_count', 1)
        delayed_start_seconds     = col_cfg.get('delayed_start_seconds', 10)
        scenario_duration_minutes = col_cfg.get('scenario_duration_minutes', 15)
        wait_for_server_seconds   = col_cfg.get('wait_for_server_seconds', 60)
        headless                  = col_cfg.get('headless', True)
        traces_output_dir         = col_cfg.get('traces_output_dir', './testlog/PHMTraces')

        params = ModernStandbyCyclingParams(
            delayed_start_seconds=delayed_start_seconds,
            scenario_duration_minutes=scenario_duration_minutes,
            cycle_count=cycle_count,
        )
        # Timeout derived from params; Config can still override explicitly.
        completion_timeout = col_cfg.get('completion_timeout_seconds', params.completion_timeout)
        logger.info(
            f"[TEST_05] Collector params: cycles={cycle_count}, "
            f"delayed_start={delayed_start_seconds}s, "
            f"duration={scenario_duration_minutes}min"
        )

        # ── Open PHM web UI via Playwright ────────────────────────────
        ui = PHMUIMonitor(host='localhost', port=1337, headless=headless)
        try:
            logger.info(f"[TEST_05] Waiting for PHM server (timeout={wait_for_server_seconds}s)")
            ui.wait_for_ready(timeout=wait_for_server_seconds)
            logger.info("[TEST_05] PHM server ready — opening browser")
            ui.open_browser(headless=False)

            # ── Run the collector session ────────────────────────────
            TestSTC547IntelRVPModernStandby._phm_start_time = datetime.now().isoformat(timespec='seconds')
            session = CollectorSession(ui)
            session.run(params)
            logger.info("[TEST_05] CollectorSession.run() finished — test is running")

            # ── Poll for completion ───────────────────────────────────
            logger.info(f"[TEST_05] Waiting for completion (timeout={completion_timeout}s)")
            completed = ui.wait_for_completion(timeout=completion_timeout)
            if not completed:
                pytest.fail("PHM collector did not complete within the configured timeout")
            TestSTC547IntelRVPModernStandby._phm_end_time = datetime.now().isoformat(timespec='seconds')
            logger.info("[TEST_05] PHM collector completed")

            # ── Collect traces ────────────────────────────────────────
            try:
                traces_src = ui.get_traces_path()
                dest_dir = Path(traces_output_dir)
                if dest_dir.exists():
                    shutil.rmtree(str(dest_dir))
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(traces_src, str(dest_dir), dirs_exist_ok=True)
                logger.info(f"[TEST_05] Traces copied: {traces_src} -> {dest_dir}")
            except Exception as exc:
                logger.warning(f"[TEST_05] Trace collection failed (non-fatal): {exc}")

        finally:
            try:
                ui.close_browser()
                logger.info("[TEST_05] Browser closed")
            except Exception as exc:
                logger.warning(f"[TEST_05] close_browser error (non-fatal): {exc}")

            try:
                mgr.terminate()
                logger.info("[TEST_05] PHM process terminated")
            except Exception as exc:
                logger.warning(f"[TEST_05] PHM terminate error (non-fatal): {exc}")

            # Safety net: force-kill by process name regardless of whether
            # terminate() succeeded.
            try:
                mgr.kill_by_name()
                logger.info("[TEST_05] PHM force-kill by name executed")
            except Exception as exc:
                logger.warning(f"[TEST_05] PHM kill_by_name error (non-fatal): {exc}")

    @pytest.mark.order(6)
    @step(6, "Verify DRIPS — SW/HW > 80%")
    def test_06_verify_drips(self, test_params):
        """
        Generate a Sleep Study report covering the PHM collection window
        (phm_start_time ... phm_end_time captured in test_05), then verify
        that every session's SW DRIPS and HW DRIPS are both > 80%.
        """
        logger.info("[TEST_06] Sleep Study DRIPS verification started")

        # Require that test_05 actually ran and captured timestamps
        if not self._phm_start_time or not self._phm_end_time:
            pytest.fail(
                "PHM timestamps not set — test_05 must complete successfully "
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
        logger.info(f"[TEST_06] Sleep Study report generated: {ss_cfg['output_path']}")

        # ── Parse SW/HW DRIPS and verify ─────────────────────────────
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
        logger.info(f"[TEST_06] Found {len(sessions)} sleep session(s)")
        for s in sessions:
            logger.info(f"[TEST_06]   Session {s.session_id}: SW={s.sw_pct}%  HW={s.hw_pct}%")

        # Guard: if every session has None DRIPS values, there is no data to
        # validate.  validate_drips skips None entries by design (short /
        # transitional sessions), so an all-None result would silently pass.
        # Treat that as a missing-data failure instead.
        sessions_with_data = [
            s for s in sessions if s.sw_pct is not None or s.hw_pct is not None
        ]
        if not sessions_with_data:
            pytest.fail(
                f"Sleep Study DRIPS check failed: all {len(sessions)} session(s) "
                f"have no DRIPS data (SW=None, HW=None). "
                f"The sleep session may be too short or the report may not "
                f"contain connected standby DRIPS metrics."
            )

        failures = validate_drips(sessions, test_params.drips_threshold, strict=True)
        if failures:
            pytest.fail("Sleep Study DRIPS check failed:\n" + "\n".join(failures))
        logger.info("[TEST_06] Sleep Study DRIPS check passed")

    @pytest.mark.order(7)
    @step(7, "PHM Visualizer — PCIe LPM check")
    def test_07_verify_pcie_lpm(self, test_params):
        """
        Re-launch PHM, open the Visualizer page, select the PCIeLPM metric,
        read the L1.2 column from the results table, and assert that the
        measured value meets the configured threshold.

        Mirrors the logic in tests/verification/phm/smoke_phm_visualizer_pcie_lpm.py.
        """
        logger.info("[TEST_07] PCIe LPM visualizer check started")

        phm_cfg = self.config['phm']
        vis_cfg_raw = self.config.get('phm_visualizer', {})

        metric_name   = vis_cfg_raw.get('metric_name', 'PCIeLPM')
        device_filter = vis_cfg_raw.get('device_filter', 'Standard NVM Express Controller') or None
        thresholds    = vis_cfg_raw.get('thresholds', {'L1.2': 90.0})
        headless      = vis_cfg_raw.get('headless', True)
        host          = vis_cfg_raw.get('host', 'localhost')
        port          = vis_cfg_raw.get('port', 1337)
        api_port      = vis_cfg_raw.get('api_port', 1338)
        pause         = vis_cfg_raw.get('pause_between_steps', 1.0)
        traces_dir    = vis_cfg_raw.get('traces_dir', None)
        output_dir    = vis_cfg_raw.get('output_dir', './testlog/PHMVisualizer')

        # ── (Re-)launch PHM ───────────────────────────────────────────
        mgr = PHMProcessManager(install_path=phm_cfg['install_path'])
        if not mgr.is_installed():
            pytest.fail(
                "PHM is not installed — cannot run Visualizer check. "
                "Ensure test_02 ran successfully."
            )
        mgr.launch()
        logger.info("[TEST_07] PHM process launched")

        try:
            cfg = VisualizerConfig(
                host=host,
                port=port,
                api_port=api_port,
                headless=headless,
                pause_between_steps=pause,
                save_output=True,
            )
            if traces_dir:
                from pathlib import Path as _Path
                cfg.traces_base_dir = _Path(traces_dir)
            if output_dir:
                cfg.output_dir = Path(output_dir)
                Path(output_dir).mkdir(parents=True, exist_ok=True)

            logger.info(
                f"[TEST_07] Visualizer params: metric={metric_name}, "
                f"device={device_filter!r}, thresholds={thresholds}"
            )

            result = run_visualizer_check(
                metric_name=metric_name,
                device_filter=device_filter,
                thresholds=thresholds,
                config=cfg,
            )
        finally:
            try:
                mgr.terminate()
                logger.info("[TEST_07] PHM process terminated")
            except Exception as exc:
                logger.warning(f"[TEST_07] PHM terminate error (non-fatal): {exc}")
            try:
                mgr.kill_by_name()
                logger.info("[TEST_07] PHM force-kill by name executed")
            except Exception as exc:
                logger.warning(f"[TEST_07] PHM kill_by_name error (non-fatal): {exc}")

        if not result.passed:
            pytest.fail(
                "PCIe LPM visualizer check failed:\n"
                + "\n".join(str(v) for v in result.verdicts)
            )
        logger.info("[TEST_07] PCIe LPM visualizer check passed")

    @pytest.mark.order(8)
    @step(8, "PHM Visualizer — PCIe LTR check")
    def test_08_verify_pcie_ltr(self, test_params):
        """
        Re-launch PHM, open the Visualizer page, select the PCIe LTR metric,
        read the Min column from the results table (in ns), and assert that
        the value is <= the configured upper-bound threshold (default 50 ms
        = 50,000,000 ns).  Rows reporting "No LTR" are automatically skipped.

        Mirrors the logic in tests/verification/phm/smoke_phm_visualizer_pcie_ltr.py.
        """
        logger.info("[TEST_08] PCIe LTR visualizer check started")

        phm_cfg = self.config['phm']
        vis_cfg_raw = self.config.get('phm_visualizer_ltr', {})

        metric_name     = vis_cfg_raw.get('metric_name', 'PCIe LTR')
        api_metric_name = vis_cfg_raw.get('api_metric_name', 'PCIe LTR')
        device_filter   = vis_cfg_raw.get('device_filter', 'Standard NVM Express Controller') or None
        thresholds      = vis_cfg_raw.get('thresholds', {})
        max_thresholds  = vis_cfg_raw.get('max_thresholds', {'Min': 50_000_000})
        headless        = vis_cfg_raw.get('headless', True)
        host            = vis_cfg_raw.get('host', 'localhost')
        port            = vis_cfg_raw.get('port', 1337)
        api_port        = vis_cfg_raw.get('api_port', 1338)
        pause           = vis_cfg_raw.get('pause_between_steps', 1.0)
        traces_dir      = vis_cfg_raw.get('traces_dir', None)
        output_dir      = vis_cfg_raw.get('output_dir', './testlog/PHMVisualizerLTR')

        # ── (Re-)launch PHM ───────────────────────────────────────────
        mgr = PHMProcessManager(install_path=phm_cfg['install_path'])
        if not mgr.is_installed():
            pytest.fail(
                "PHM is not installed — cannot run Visualizer check. "
                "Ensure test_02 ran successfully."
            )
        mgr.launch()
        logger.info("[TEST_08] PHM process launched")

        try:
            cfg = VisualizerConfig(
                host=host,
                port=port,
                api_port=api_port,
                headless=headless,
                pause_between_steps=pause,
                save_output=True,
            )
            if traces_dir:
                cfg.traces_base_dir = Path(traces_dir)
            if output_dir:
                cfg.output_dir = Path(output_dir)
                Path(output_dir).mkdir(parents=True, exist_ok=True)

            logger.info(
                f"[TEST_08] Visualizer params: metric={metric_name}, "
                f"device={device_filter!r}, max_thresholds={max_thresholds}"
            )

            result = run_visualizer_check(
                metric_name=metric_name,
                api_metric_name=api_metric_name,
                device_filter=device_filter,
                thresholds=thresholds,
                max_thresholds=max_thresholds,
                config=cfg,
            )
        finally:
            try:
                mgr.terminate()
                logger.info("[TEST_08] PHM process terminated")
            except Exception as exc:
                logger.warning(f"[TEST_08] PHM terminate error (non-fatal): {exc}")
            try:
                mgr.kill_by_name()
                logger.info("[TEST_08] PHM force-kill by name executed")
            except Exception as exc:
                logger.warning(f"[TEST_08] PHM kill_by_name error (non-fatal): {exc}")

        if not result.passed:
            pytest.fail(
                "PCIe LTR visualizer check failed:\n"
                + "\n".join(str(v) for v in result.verdicts)
            )
        logger.info("[TEST_08] PCIe LTR visualizer check passed")

    @pytest.mark.order(9)
    @step(9, "PHM Visualizer — OS Modern Standby check")
    def test_09_verify_os_modern_standby(self, test_params):
        """
        Re-launch PHM, open the Visualizer page, select the OS Events parent
        node and exclusively filter to the Modern Standby child item, then
        assert that the Entered column value meets the configured lower-bound
        threshold (default >= 90%).

        Mirrors the logic in
        tests/verification/phm/smoke_phm_visualizer_os_modern_standby.py.
        """
        logger.info("[TEST_09] OS Events / Modern Standby visualizer check started")

        phm_cfg = self.config['phm']
        vis_cfg_raw = self.config.get('phm_visualizer_os_ms', {})

        metric_name     = vis_cfg_raw.get('metric_name', 'OS Events')
        api_metric_name = vis_cfg_raw.get('api_metric_name', 'OS Events')
        device_filter   = vis_cfg_raw.get('device_filter', 'Modern Standby') or None
        thresholds      = vis_cfg_raw.get('thresholds', {'Entered': 90.0})
        max_thresholds  = vis_cfg_raw.get('max_thresholds', {})
        headless        = vis_cfg_raw.get('headless', True)
        host            = vis_cfg_raw.get('host', 'localhost')
        port            = vis_cfg_raw.get('port', 1337)
        api_port        = vis_cfg_raw.get('api_port', 1338)
        pause           = vis_cfg_raw.get('pause_between_steps', 1.0)
        traces_dir      = vis_cfg_raw.get('traces_dir', None)
        output_dir      = vis_cfg_raw.get('output_dir', './testlog/PHMVisualizerOSMS')

        # ── (Re-)launch PHM ───────────────────────────────────────────
        mgr = PHMProcessManager(install_path=phm_cfg['install_path'])
        if not mgr.is_installed():
            pytest.fail(
                "PHM is not installed — cannot run Visualizer check. "
                "Ensure test_02 ran successfully."
            )
        mgr.launch()
        logger.info("[TEST_09] PHM process launched")

        try:
            cfg = VisualizerConfig(
                host=host,
                port=port,
                api_port=api_port,
                headless=headless,
                pause_between_steps=pause,
                save_output=True,
            )
            if traces_dir:
                cfg.traces_base_dir = Path(traces_dir)
            if output_dir:
                cfg.output_dir = Path(output_dir)
                Path(output_dir).mkdir(parents=True, exist_ok=True)

            logger.info(
                f"[TEST_09] Visualizer params: metric={metric_name}, "
                f"device_filter={device_filter!r}, thresholds={thresholds}"
            )

            result = run_visualizer_check(
                metric_name=metric_name,
                device_filter=device_filter,
                api_metric_name=api_metric_name,
                thresholds=thresholds,
                max_thresholds=max_thresholds,
                config=cfg,
            )
        finally:
            try:
                mgr.terminate()
                logger.info("[TEST_09] PHM process terminated")
            except Exception as exc:
                logger.warning(f"[TEST_09] PHM terminate error (non-fatal): {exc}")
            try:
                mgr.kill_by_name()
                logger.info("[TEST_09] PHM force-kill by name executed")
            except Exception as exc:
                logger.warning(f"[TEST_09] PHM kill_by_name error (non-fatal): {exc}")

        if not result.passed:
            pytest.fail(
                "OS Events / Modern Standby visualizer check failed:\n"
                + "\n".join(str(v) for v in result.verdicts)
            )
        logger.info("[TEST_09] OS Events / Modern Standby visualizer check passed")
