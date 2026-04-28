"""
STC-XXXX: Diskercise I/O Stress Test (Pytest Framework)

End-to-end integration test that runs Diskercise.exe against the primary SSD
and verifies no I/O failure popup appears within the test duration.

Workflow:
    Step 1  — Precondition: clean testlog, remove stale reboot state.
    Step 2  — Install Tools: install Diskercise and SmiCli via Chocolatey.
    Step 3  — Apply OsConfig: disable MemoryDiagnostic tasks, switch to
              high-performance power plan, enable auto admin logon.
    Step 4  — Clean Environment: kill stale Diskercise processes, reboot for a
              clean platform environment.
    Step 5  — Run Diskercise: launch Diskercise.exe, apply GUI config, run
              I/O stress test for the configured duration, then stop.
    Step 6  — Verify Result: assert no failure was detected during the run.

Requirements:
    - Windows OS with Administrator privileges.
    - Diskercise installed at C:\\tools\\Diskercise\\ (via Chocolatey).
    - pywinauto installed (win32 backend).

Environment variables:
    SSD_TESTKIT_AUTO_LOGIN_PASSWORD   Password for auto admin logon
    DISKERCISE_PATH                   Override Diskercise.exe directory

Run:
    pytest tests/integration/test_case/stcXXXX_diskercise/test_main.py -v -s
"""

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.reboot_manager import RebootManager
from framework.test_utils import take_screenshot, log_dut_info
from lib.logger import get_module_logger, clear_log_files
from lib.testtool.tool_installer import ToolInstaller
from lib.testtool.osconfig import OsConfigController
from lib.testtool.osconfig.state_manager import OsConfigStateManager
from lib.testtool.diskercise import DiskerciseController

logger = get_module_logger(__name__)

_SCREENSHOT_DIR = './testlog/diskercise/screenshots'


@pytest.mark.integration
@pytest.mark.feature_diskercise
@pytest.mark.slow
class TestSTC_XXXX_Diskercise(BaseTestCase):
    """
    STC-XXXX: Diskercise I/O stress test — single-instance mode.

    Runs Diskercise.exe against the primary SSD for the configured duration
    and verifies no "Operation Failure" popup appears.
    """

    _osconfig_controller: "OsConfigController | None" = None

    # Shared controller between test_05 (run) and test_06 (verify)
    _ctrl: "DiskerciseController | None" = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _take_screenshot(label: str) -> None:
        path = take_screenshot(label, _SCREENSHOT_DIR)
        if path:
            logger.info(f"[SCREENSHOT] Saved: {path.name}")
        else:
            logger.debug(f"[SCREENSHOT] Skipped or failed: '{label}'")

    @staticmethod
    def _log_dut_info() -> None:
        log_dut_info(logger)

    # ------------------------------------------------------------------
    # Step 1 — Precondition
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition")
    def test_01_precondition(self):
        """Clean testlog (preserve Runcard.ini) and remove stale reboot state."""
        logger.info("[TEST_01] Cleaning testlog directory...")
        self._cleanup_testlog_directory()
        clear_log_files()
        Path(self.log_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"[TEST_01] log_path ready: {Path(self.log_path).resolve()}")

        state_file = Path(RebootManager.STATE_FILE)
        if state_file.exists():
            state_file.unlink()
            self.reboot_mgr.state = self.reboot_mgr._load_state()
            logger.info(f"[TEST_01] Removed stale reboot state: {state_file}")
        else:
            logger.info("[TEST_01] No stale reboot state found")

        logger.info("[TEST_01] Precondition complete")

    # ------------------------------------------------------------------
    # Step 2 — Install Tools
    # ------------------------------------------------------------------

    @pytest.mark.order(2)
    @step(2, "Install tools")
    def test_02_install_tools(self):
        """Install tools declared in Config/tools.yaml (diskercise)."""
        _tools_yaml = Path(__file__).parent / "Config" / "tools.yaml"
        logger.info(f"[TEST_02] Installing tools from: {_tools_yaml}")
        ToolInstaller(_tools_yaml).install_all()
        logger.info("[TEST_02] Tools installed")

    # ------------------------------------------------------------------
    # Step 3 — Apply OS Configuration
    # ------------------------------------------------------------------

    @pytest.mark.order(3)
    @step(3, "Apply OS configuration")
    def test_03_apply_osconfig(self):
        """Apply OS configuration from Config/osconfig.yaml.

        Disables MemoryDiagnostic tasks, switches to high-performance power
        plan, and enables auto admin logon for post-reboot recovery.
        """
        controller = OsConfigController(
            profile=self._osconfig_profile,
            state_manager=OsConfigStateManager(),
        )
        controller.apply_all()
        TestSTC_XXXX_Diskercise._osconfig_controller = controller
        logger.info("[TEST_03] OsConfig applied successfully")

    # ------------------------------------------------------------------
    # Step 4 — Clean Environment + Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(4)
    @step(4, "Clean Environment")
    def test_04_clean_environment(self, request: pytest.FixtureRequest):
        """Kill stale Diskercise processes, then reboot for a clean environment.

        RebootManager persists state, writes the startup BAT, issues
        shutdown /r, and calls os._exit(0).  pytest resumes at
        test_05_run_diskercise after the system comes back up (Run #2).

        # os._exit(0) is called inside setup_reboot — code below never executes
        """
        result = subprocess.run(
            ['taskkill', '/F', '/IM', 'Diskercise.exe'],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            logger.info(f"[TEST_04] Killed stale Diskercise.exe: {result.stdout.strip()}")
        else:
            logger.info("[TEST_04] No stale Diskercise.exe process found")

        # Pre-mark BEFORE setup_reboot() calls os._exit(0) to avoid infinite reboot loop.
        self.reboot_mgr.pre_mark_completed(request.node.name)

        logger.info("[TEST_04] Issuing reboot for clean platform environment...")
        self.reboot_mgr.setup_reboot(
            delay=10,
            reason="test_04_clean_environment: clean platform environment before Diskercise",
            test_file=__file__,
        )
        # os._exit(0) called inside setup_reboot — code below never executes

    # ------------------------------------------------------------------
    # Step 5 — Run Diskercise
    # ------------------------------------------------------------------

    @pytest.mark.order(5)
    @step(5, "Run Diskercise I/O stress test")
    def test_05_run_diskercise(self):
        """Launch Diskercise.exe, apply GUI config, run stress test, wait for completion.

        Configuration is loaded from Config/Config.json → 'diskercise' key.
        The controller scans for an "Operation Failure" popup every
        check_interval_seconds throughout the test duration and sets
        ctrl.status to False if any failure is detected.
        """
        logger.info("[TEST_05] Diskercise run started")

        # ── DUT topology ──────────────────────────────────────────────
        self._log_dut_info()

        # ── Config summary ────────────────────────────────────────────
        diskercise_cfg = self.config['diskercise']
        duration = diskercise_cfg.get('test_duration_minutes', 30)
        logger.info(
            "[TEST_05] Diskercise config:\n"
            f"  thread_count          = {diskercise_cfg.get('thread_count', 4)}\n"
            f"  file_size_mb          = {diskercise_cfg.get('file_size_mb', 1024)}\n"
            f"  access_size_kb        = {diskercise_cfg.get('access_size_kb', 4)}\n"
            f"  read_ratio            = {diskercise_cfg.get('read_ratio', 50)}%\n"
            f"  write_ratio           = {diskercise_cfg.get('write_ratio', 50)}%\n"
            f"  data_type             = {diskercise_cfg.get('data_type', 0)}\n"
            f"  buffered_io           = {diskercise_cfg.get('buffered_io', True)}\n"
            f"  test_duration_minutes = {duration}"
        )

        # ── Screenshot: desktop state before launch ────────────────────
        self._take_screenshot("before_diskercise_launch")

        ctrl = DiskerciseController(
            thread_count=diskercise_cfg.get('thread_count', 4),
            file_size_mb=diskercise_cfg.get('file_size_mb', 1024),
            access_size_kb=diskercise_cfg.get('access_size_kb', 4),
            read_ratio=diskercise_cfg.get('read_ratio', 50),
            write_ratio=diskercise_cfg.get('write_ratio', 50),
            data_type=diskercise_cfg.get('data_type', 0),
            buffered_io=diskercise_cfg.get('buffered_io', True),
            test_duration_minutes=duration,
            log_path='./testlog/diskercise',
        )

        logger.info("[TEST_05] Starting DiskerciseController thread...")
        ctrl.start()

        # Wait up to (duration + 5 min) for the thread to finish
        timeout_seconds = duration * 60 + 300
        logger.info(f"[TEST_05] Waiting for completion (timeout={timeout_seconds}s)...")
        ctrl.join(timeout=timeout_seconds)

        if ctrl.is_alive():
            logger.error("[TEST_05] Diskercise thread still alive after timeout — forcing stop")
            self._take_screenshot("diskercise_timeout")
            ctrl.stop()
            ctrl.join(timeout=30)
            pytest.fail(
                f"[TEST_05] Diskercise did not complete within {timeout_seconds}s"
            )

        TestSTC_XXXX_Diskercise._ctrl = ctrl
        logger.info(
            f"[TEST_05] Diskercise run finished — status={ctrl.status}, "
            f"error_count={ctrl.error_count}"
        )
        if ctrl.failure_message:
            logger.warning(f"[TEST_05] failure_message: {ctrl.failure_message}")

        # ── Screenshot: final state after run ─────────────────────────
        self._take_screenshot("after_diskercise_run")

    # ------------------------------------------------------------------
    # Step 6 — Verify Result
    # ------------------------------------------------------------------

    @pytest.mark.order(6)
    @step(6, "Verify Diskercise result")
    def test_06_verify_result(self):
        """Assert that no Diskercise failure was detected during the run.

        Passes if ctrl.status is True (no 'Operation Failure' popup appeared
        and the test ran for the full configured duration without error).
        """
        ctrl = TestSTC_XXXX_Diskercise._ctrl
        if ctrl is None:
            pytest.fail("[TEST_06] DiskerciseController not initialised — test_05 may have failed")

        logger.info(
            f"[TEST_06] Verifying result — "
            f"status={ctrl.status}, error_count={ctrl.error_count}"
        )

        failure_message = getattr(ctrl, 'failure_message', None)
        if failure_message:
            logger.error(f"[TEST_06] failure_message: {failure_message}")

        assert ctrl.status is True, (
            f"[TEST_06] Diskercise test FAILED"
            + (f": {failure_message}" if failure_message else "")
        )

        logger.info("[TEST_06] Diskercise test PASSED — no I/O failure detected")


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--log-file=./log/pytest.log",
        "--log-file-level=INFO",
        "--log-file-format=%(asctime)s [%(levelname)s] %(message)s",
        "--log-file-date-format=%Y-%m-%d %H:%M:%S",
    ])
