"""
Boot Performance (Full Boot) Configured-Job Workflow Integration Test

Step-based end-to-end test for running BPFB via the WAC Configure Job path.
Survives the full OS reboot that WAC triggers as part of the assessment,
using RebootManager to persist state and auto-restart pytest.

Workflow:
    Step 1 — Precondition: clean up stale WAC directories (first boot only).
    Step 2 — Open WAC, configure BPFB (Iterations=1), save custom job,
             connect launcher, persist reboot state, click Start.
             WAC will perform a full cold reboot immediately after Start.
    Step 3 — After reboot: connect to WAC, wait for the View Results page,
             read errors / warnings / result path.
    Step 4 — Assert final result artefacts exist.

Requirements:
    - Windows ADK (wac.exe) must be installed.
    - Must run as Administrator on a supported Windows build (22000/22621/26100).

Environment variables:
    ADK_BPFB_JOB_NAME   Job name in the Save Custom Job dialog
                        (default: BPFB_Workflow_Test)
    ADK_BPFB_TIMEOUT    Max seconds to wait for the assessment result
                        (default: 7200 — 2 hours)
    ADK_LOG_DIR         Override the base directory for log output

Run:
    pytest tests/integration/lib/testtool/test_windows_adk/test_bpfb_workflow.py -v -s
"""

import os
import subprocess
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.reboot_manager import RebootManager
from lib.logger import get_module_logger, clear_log_files
from lib.testtool.windows_adk import ADKController
from lib.testtool.windows_adk.config import WAC_EXE, get_build_number
from lib.testtool.windows_adk.result_reader import WACRunResult
from lib.testtool.windows_adk.version_adapter import VersionAdapter

logger = get_module_logger(__name__)


@pytest.mark.integration
@pytest.mark.requires_windows_adk
@pytest.mark.slow
class TestBPFBWorkflow(BaseTestCase):
    """
    Reboot-survivable end-to-end test for the BPFB Configure Job workflow.

    Inherits BaseTestCase so that setup_teardown_function (autouse) handles
    skip-completed logic automatically on every recovery boot.
    """

    # Class-level state: populated by test_03, consumed by test_04
    _wac_result: "WACRunResult | None" = None

    # ------------------------------------------------------------------
    # Class-level fixture — overrides BaseTestCase.setup_teardown_class
    # ------------------------------------------------------------------

    @pytest.fixture(scope="class", autouse=True)
    def setup_test_class(self, request):
        """Initialise working directory, VersionAdapter, and RebootManager."""
        cls = request.cls
        cls.original_cwd = os.getcwd()

        test_dir = cls._setup_working_directory(__file__)

        # Resolve log path: ADK_LOG_DIR env var or test directory
        base = os.getenv("ADK_LOG_DIR")
        cls.log_path = str(Path(base) / "bpfb_workflow") if base else str(test_dir / "testlog" / "bpfb_workflow")
        Path(cls.log_path).mkdir(parents=True, exist_ok=True)

        cls.adapter = VersionAdapter(get_build_number())
        cls.reboot_mgr = RebootManager(total_tests=cls._count_test_methods())

        phase = "POST-REBOOT (recovering)" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
        logger.info(f"[SETUP] Phase        : {phase}")
        logger.info(f"[SETUP] reboot_count : {cls.reboot_mgr.state.get('reboot_count', 0)}")
        logger.info(f"[SETUP] completed    : {cls.reboot_mgr.state.get('completed_tests', [])}")
        logger.info(f"[SETUP] log_path     : {cls.log_path}")

        yield

        cls._teardown_reboot_manager()
        logger.info(f"{cls.__name__} session complete")
        os.chdir(cls.original_cwd)

    # ------------------------------------------------------------------
    # Step 1 — Precondition (first boot only)
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition — clean WAC directories")
    def test_01_precondition(self, adk_env, check_environment):
        """Remove stale WAC result/job/test directories before the run."""
        # Kill any running WAC / assessment engine so file locks are released
        for proc in ("wac.exe", "axe.exe"):
            subprocess.run(["taskkill", "/f", "/im", proc],
                           capture_output=True)
        time.sleep(1)

        # Clear log files so this run starts with a clean app.log.
        clear_log_files()
        Path(self.log_path).mkdir(parents=True, exist_ok=True)

        # Remove stale reboot state so a re-run always starts fresh.
        state_file = Path(RebootManager.STATE_FILE)
        if state_file.exists():
            state_file.unlink()
            self.reboot_mgr.state = self.reboot_mgr._load_state()
            logger.info(f"[TEST_01] Removed stale reboot state: {state_file}")

        ctrl = ADKController(config={"log_path": self.log_path})
        ctrl.cleanup_dirs()
        logger.info("[TEST_01] WAC directories cleaned")

    # ------------------------------------------------------------------
    # Step 2 — Configure BPFB and click Start (triggers full reboot)
    # ------------------------------------------------------------------

    @pytest.mark.order(2)
    @step(2, "Configure BPFB and click Start")
    def test_02_configure_and_start(self, adk_env, check_environment):
        """
        Open WAC, configure BPFB with Iterations=1, save the custom job,
        connect the Assessment Launcher.

        RebootManager.prepare_for_external_reboot() is called BEFORE
        click_start() so that state is persisted and the auto-start BAT is
        written while the process is still running.  WAC performs a full cold
        reboot immediately after Start; pytest auto-resumes at Step 3.
        """
        job_name = os.getenv("ADK_BPFB_JOB_NAME", "BPFB_Workflow_Test")
        ctrl = ADKController(config={"log_path": self.log_path})

        ctrl._ui.open(WAC_EXE)
        ctrl._ui.select_bpfb_configured_job(num_iters=1)
        ctrl._ui.save_custom_job(job_name)
        ctrl._ui.connect_launcher()

        # Persist state BEFORE clicking Start — the machine will reboot.
        self.reboot_mgr.prepare_for_external_reboot(
            step_name="test_02_configure_and_start",
            test_file=__file__,
        )

        logger.info("[TEST_02] Clicking Start — machine will reboot shortly")
        ctrl._ui.click_start()

        # Fallback wait in case reboot is delayed (e.g. dry-run environment).
        # Wall-clock detection: if the 120-second sleep actually takes >>120 s
        # of real time, the machine rebooted and resumed mid-sleep.  In that
        # case a second pytest process has already been started by the startup
        # BAT.  Exit this (original) process to prevent duplicate test_03
        # execution.
        logger.info("[TEST_02] Waiting for reboot...")
        _t_click = time.time()
        time.sleep(120)
        _wall = time.time() - _t_click
        if _wall > 300:
            logger.info(
                "[TEST_02] Reboot detected (wall time=%.0fs) — "
                "exiting so startup BAT handles test_03+", _wall
            )
            os._exit(0)

    # ------------------------------------------------------------------
    # Step 3 — Wait for assessment result (runs after reboot)
    # ------------------------------------------------------------------

    @pytest.mark.order(3)
    @step(3, "Wait for WAC assessment result")
    def test_03_wait_result(self, adk_env, check_environment):
        """
        Connect to WAC after the post-BPFB cold reboot and wait for the
        View Results page to appear.

        WAC auto-resumes the assessment after reboot; when finished it
        switches to the View Results page.  We read:
          - Total errors / warnings from the Run information grid
          - The Results filesystem path from the System information panel

        Pass criteria: errors == 0.
        """
        timeout = int(os.getenv("ADK_BPFB_TIMEOUT", "7200"))
        ctrl = ADKController(config={"log_path": self.log_path})

        # ── Verify this was a cold boot, not a Fast Startup resume ────────
        # BPFB expects a full cold reboot (type=2).  A Fast Startup resume
        # (type=1) would indicate WAC used hibernate instead, which is unexpected.
        # Event ID 1 data[0]=1  → Fast Startup resume (hibernate)
        # Event ID 1 data[0]=2  → Cold boot (expected for BPFB)
        try:
            ps_check = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-WinEvent -LogName System -MaxEvents 300 "
                    "| Where-Object { $_.Id -eq 1 -and $_.ProviderName -eq "
                    "'Microsoft-Windows-Kernel-Power' } "
                    "| Select-Object -First 1 -ExpandProperty Properties "
                    "| Select-Object -First 1 -ExpandProperty Value",
                ],
                capture_output=True, text=True, timeout=30,
            )
            boot_type = ps_check.stdout.strip()
            if boot_type == "2":
                logger.info("[TEST_03] Boot type confirmed: cold boot (expected for BPFB)")
            elif boot_type == "1":
                logger.warning(
                    "[TEST_03] Unexpected Fast Startup resume detected — "
                    "expected a cold boot for BPFB.  Proceeding anyway."
                )
            else:
                logger.warning(f"[TEST_03] Boot type unknown (value={boot_type!r}) — proceeding")
        except Exception as exc:
            logger.warning(f"[TEST_03] Boot-type check failed (non-fatal): {exc}")

        # debug_enumerate=True logs all UI element IDs on first run.
        # Flip to False once auto_ids are confirmed on this build.
        wac_result = ctrl._ui.read_view_results(
            timeout=timeout,
            debug_enumerate=True,
        )

        logger.info(
            "[TEST_03] errors=%d  warnings=%d  analysis_complete=%s",
            wac_result.errors, wac_result.warnings, wac_result.analysis_complete,
        )
        logger.info("[TEST_03] machine      : %s", wac_result.machine_name)
        logger.info("[TEST_03] run_time     : %s", wac_result.run_time)
        logger.info("[TEST_03] result_path  : %s", wac_result.result_path)

        # Store for step 4 verification
        TestBPFBWorkflow._wac_result = wac_result

        assert wac_result.errors == 0, (
            f"BPFB assessment completed with {wac_result.errors} error(s). "
            f"Results path: {wac_result.result_path}"
        )

    # ------------------------------------------------------------------
    # Step 4 — Verify result artefacts
    # ------------------------------------------------------------------

    @pytest.mark.order(4)
    @step(4, "Verify result artefacts")
    def test_04_verify(self, adk_env, check_environment):
        """Assert expected result files exist using the path reported by WAC."""
        wac_result = getattr(TestBPFBWorkflow, "_wac_result", None)

        assert wac_result is not None, (
            "test_03_wait_result did not store a WACRunResult — "
            "ensure test_03 ran and passed before test_04."
        )
        assert wac_result.result_path, (
            f"WAC did not report a Results path. "
            f"errors={wac_result.errors}  warnings={wac_result.warnings}\n"
            "Check app.log for [ViewResults DEBUG] entries to diagnose."
        )

        result_dir = Path(wac_result.result_path)
        assert result_dir.is_dir(), (
            f"WAC Results directory does not exist: {result_dir}"
        )

        axelog = result_dir / "AxeLog.txt"
        assert axelog.exists(), f"AxeLog.txt not found in {result_dir}"
        logger.info(f"[TEST_04] AxeLog.txt verified: {axelog}")
