"""
Boot Performance (Fast Startup) Configured-Job Workflow Integration Test

Step-based end-to-end test for running BPFS via the WAC Configure Job path.
Survives the system hibernate/reboot that WAC triggers as part of the
assessment, using RebootManager to persist state and auto-restart pytest.

Workflow:
    Step 1 — Precondition: clean up stale WAC directories (first boot only).
    Step 2 — Open WAC, configure BPFS (Iterations=1, wake timers ON), save
             custom job, connect launcher, persist reboot state, click Start.
             WAC will hibernate the machine immediately after Start is clicked.
    Step 3 — After reboot: poll WAC result directory until the assessment
             completes, then verify AxeLog passes.
    Step 4 — Assert final result artefacts exist.

Requirements:
    - Windows ADK (wac.exe) must be installed.
    - Must run as Administrator on a supported Windows build (22000/22621/26100).
    - Fast Startup must be enabled in Power settings.
    - Wake timers must be enabled (Group Policy / Power plan).

Environment variables:
    ADK_BPFS_JOB_NAME   Job name in the Save Custom Job dialog
                        (default: BPFS_Workflow_Test)
    ADK_BPFS_TIMEOUT    Max seconds to wait for the assessment result
                        (default: 7200 — 2 hours)
    ADK_LOG_DIR         Override the base directory for log output

Run:
    pytest tests/integration/lib/testtool/test_windows_adk/test_bpfs_workflow.py -v -s
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
from lib.logger import get_module_logger
from lib.testtool.windows_adk import ADKController
from lib.testtool.windows_adk.config import WAC_EXE, get_build_number
from lib.testtool.windows_adk.result_parser import parse_axelog
from lib.testtool.windows_adk.version_adapter import VersionAdapter

logger = get_module_logger(__name__)


@pytest.mark.integration
@pytest.mark.requires_windows_adk
@pytest.mark.slow
class TestBPFSWorkflow(BaseTestCase):
    """
    Reboot-survivable end-to-end test for the BPFS Configure Job workflow.

    Inherits BaseTestCase so that setup_teardown_function (autouse) handles
    skip-completed logic automatically on every recovery boot.
    """

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
        cls.log_path = str(Path(base) / "bpfs_workflow") if base else str(test_dir / "testlog" / "bpfs_workflow")
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

        ctrl = ADKController(config={"log_path": self.log_path})
        ctrl.cleanup_dirs()
        logger.info("[TEST_01] WAC directories cleaned")

    # ------------------------------------------------------------------
    # Step 2 — Configure BPFS and click Start (triggers hibernate)
    # ------------------------------------------------------------------

    @pytest.mark.order(2)
    @step(2, "Configure BPFS and click Start")
    def test_02_configure_and_start(self, adk_env, check_environment):
        """
        Open WAC, configure BPFS with Iterations=1, save the custom job,
        connect the Assessment Launcher.

        RebootManager.prepare_for_external_reboot() is called BEFORE
        click_start() so that state is persisted and the auto-start BAT is
        written while the process is still running.  WAC hibernates the
        machine immediately after Start; pytest auto-resumes at Step 3.
        """
        job_name = os.getenv("ADK_BPFS_JOB_NAME", "BPFS_Workflow_Test")
        ctrl = ADKController(config={"log_path": self.log_path})

        ctrl._ui.open(WAC_EXE)
        ctrl._ui.select_bpfs_configured_job(num_iters=1, auto_boot=True)
        ctrl._ui.save_custom_job(job_name)
        ctrl._ui.connect_launcher()

        # Persist state BEFORE clicking Start — the machine will hibernate.
        self.reboot_mgr.prepare_for_external_reboot(
            step_name="test_02_configure_and_start",
            test_file=__file__,
        )

        logger.info("[TEST_02] Clicking Start — machine will hibernate shortly")
        ctrl._ui.click_start()

        # Fallback wait in case hibernate is delayed (e.g. dry-run environment).
        logger.info("[TEST_02] Waiting for hibernate...")
        time.sleep(120)

    # ------------------------------------------------------------------
    # Step 3 — Wait for assessment result (runs after reboot)
    # ------------------------------------------------------------------

    @pytest.mark.order(3)
    @step(3, "Wait for WAC assessment result")
    def test_03_wait_result(self, adk_env, check_environment):
        """
        Poll the WAC result directory until the assessment completes.

        WAC auto-resumes the assessment on wakeup; when finished it moves
        the in-flight directory to the final Assessment Results directory.
        """
        result_dir = self.adapter.get_result_dir()
        timeout = int(os.getenv("ADK_BPFS_TIMEOUT", "7200"))
        deadline = time.time() + timeout
        result_subdir = None

        while time.time() < deadline:
            if os.path.isdir(result_dir):
                subdirs = [
                    d for d in os.listdir(result_dir)
                    if os.path.isdir(os.path.join(result_dir, d))
                ]
                if subdirs:
                    result_subdir = subdirs[0]
                    break
            logger.info("[TEST_03] Waiting for WAC result directory...")
            time.sleep(10)

        assert result_subdir, (
            f"Timed out after {timeout}s waiting for WAC result in {result_dir}"
        )
        logger.info(f"[TEST_03] Result directory: {result_subdir}")

        axelog = os.path.join(result_dir, result_subdir, "AxeLog.txt")
        ok, msg = parse_axelog(axelog)
        assert ok, f"BPFS assessment failed: {msg}"
        logger.info(f"[TEST_03] Assessment passed: {msg}")

    # ------------------------------------------------------------------
    # Step 4 — Verify result artefacts
    # ------------------------------------------------------------------

    @pytest.mark.order(4)
    @step(4, "Verify result artefacts")
    def test_04_verify(self, adk_env, check_environment):
        """Assert that expected result files exist in the WAC result directory."""
        result_dir = Path(self.adapter.get_result_dir())
        subdirs = [p for p in result_dir.iterdir() if p.is_dir()] if result_dir.is_dir() else []
        assert subdirs, f"No result subdirectory found under {result_dir}"

        axelog = subdirs[0] / "AxeLog.txt"
        assert axelog.exists(), f"AxeLog.txt not found in {subdirs[0]}"
        logger.info(f"[TEST_04] AxeLog.txt verified: {axelog}")

