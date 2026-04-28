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

    # Shared between test_05 (run) and test_06 (verify)
    _ctrl: "DiskerciseController | None" = None
    _results: list = []  # [{set, config, status, error_count, failure_message}, ...]

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
    @pytest.mark.skip(reason="Test")
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
        """Execute every config set in Config.json → 'diskercise_configs' sequentially.

        For each set, launches Diskercise.exe, applies GUI config, waits for
        the configured duration, stops, and records the result.  All sets are
        run regardless of individual pass/fail; test_06 performs the final
        assertion.
        """
        logger.info("[TEST_05] Diskercise multi-config run started")
        self._log_dut_info()
        self._take_screenshot("before_diskercise_launch")

        defaults = self.config.get('diskercise_defaults', {})
        cfg_sets = self.config.get('diskercise_configs', [])
        if not cfg_sets:
            pytest.fail("[TEST_05] No 'diskercise_configs' found in Config.json")

        total = len(cfg_sets)
        results = []

        for idx, cfg_set in enumerate(cfg_sets):
            set_num = idx + 1
            merged = {**defaults, **cfg_set}
            duration = merged.get('test_duration_minutes', 1)
            log_path = f'./testlog/diskercise/set_{set_num:02d}'

            logger.info(
                f"[TEST_05] ── Config set {set_num}/{total} ──────────────────────────"
            )
            logger.info(
                f"[TEST_05]   thread={merged.get('thread_count')}  "
                f"file={merged.get('file_size_mb')}MB  "
                f"access={merged.get('access_size_kb')}kB  "
                f"R/W={merged.get('read_ratio')}/{merged.get('write_ratio')}  "
                f"data_type={merged.get('data_type')}  "
                f"buffered={merged.get('buffered_io')}  "
                f"verify_immd={merged.get('adv_verify_immediate')}  "
                f"duration={duration}min"
            )

            ctrl = DiskerciseController(
                thread_count=merged.get('thread_count', 1),
                file_size_mb=merged.get('file_size_mb', 1),
                access_size_kb=merged.get('access_size_kb', 4),
                read_ratio=merged.get('read_ratio', 4),
                write_ratio=merged.get('write_ratio', 1),
                data_type=merged.get('data_type', 0),
                buffered_io=merged.get('buffered_io', True),
                adv_write_signatures=merged.get('adv_write_signatures', True),
                adv_verify_immediate=merged.get('adv_verify_immediate', False),
                adv_pause_all_asap=merged.get('adv_pause_all_asap', True),
                adv_pulse_com1=merged.get('adv_pulse_com1', False),
                test_duration_minutes=duration,
                log_path=log_path,
            )

            ctrl.start()
            timeout_seconds = duration * 60 + 300
            ctrl.join(timeout=timeout_seconds)

            if ctrl.is_alive():
                logger.error(
                    f"[TEST_05] Set {set_num}: thread still alive after {timeout_seconds}s — forcing stop"
                )
                self._take_screenshot(f"set_{set_num:02d}_timeout")
                ctrl.stop()
                ctrl.join(timeout=30)
                results.append({
                    'set': set_num,
                    'config': cfg_set,
                    'status': False,
                    'error_count': ctrl.error_count,
                    'failure_message': f'Timeout after {timeout_seconds}s',
                })
            else:
                results.append({
                    'set': set_num,
                    'config': cfg_set,
                    'status': ctrl.status,
                    'error_count': ctrl.error_count,
                    'failure_message': ctrl.failure_message,
                })

            tag = 'PASS' if ctrl.status is True else 'FAIL'
            logger.info(f"[TEST_05] Set {set_num}/{total} → {tag}")
            self._take_screenshot(f"set_{set_num:02d}_after_run")
            TestSTC_XXXX_Diskercise._ctrl = ctrl

        TestSTC_XXXX_Diskercise._results = results
        passed = sum(1 for r in results if r['status'] is True)
        logger.info(
            f"[TEST_05] All {total} config set(s) done — {passed} passed, "
            f"{total - passed} failed"
        )

    # ------------------------------------------------------------------
    # Step 6 — Verify Result
    # ------------------------------------------------------------------

    @pytest.mark.order(6)
    @step(6, "Verify Diskercise result")
    def test_06_verify_result(self):
        """Summarise all config-set results and fail if any set did not pass."""
        results = TestSTC_XXXX_Diskercise._results
        if not results:
            pytest.fail("[TEST_06] No results recorded — test_05 may have failed to run")

        logger.info(f"[TEST_06] Results summary ({len(results)} config set(s)):")
        for r in results:
            tag = 'PASS' if r['status'] is True else 'FAIL'
            cfg = r['config']
            logger.info(
                f"  Set {r['set']:2d}: {tag}  "
                f"thread={cfg.get('thread_count')}  "
                f"file={cfg.get('file_size_mb')}MB  "
                f"access={cfg.get('access_size_kb')}kB  "
                f"R/W={cfg.get('read_ratio')}/{cfg.get('write_ratio')}  "
                f"data_type={cfg.get('data_type')}  "
                f"buffered={cfg.get('buffered_io')}  "
                f"verify_immd={cfg.get('adv_verify_immediate')}"
                + (f"  → {r['failure_message']}" if r['failure_message'] else "")
            )

        failed = [r for r in results if r['status'] is not True]
        if failed:
            msgs = [
                f"Set {r['set']}: {r['failure_message'] or 'status=False'}"
                for r in failed
            ]
            pytest.fail(
                f"[TEST_06] {len(failed)} config set(s) FAILED:\n" + "\n".join(msgs)
            )

        logger.info(f"[TEST_06] All {len(results)} config set(s) PASSED")


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
