"""
Boot Performance (Fast Startup) Configured-Job Workflow Integration Test

Verifies the complete WAC UI workflow for running a configured BPFS assessment:

    Step 1 — Open Windows Assessment Console (WAC).
    Step 2 — Click 'Run Individual Assessments' in the left panel and select
              'Boot performance (Fast Startup)'.
    Step 3 — Click 'Configure' (bottom-right) to open the Configure Job page.
    Step 4 — In the BPFS settings pane:
                • Uncheck 'Use recommended settings'
                • Set Number of Iterations = 1
                • Ensure 'Use wake timers to automate boot' is checked
    Step 5 — Click 'Overview' in the left panel and check
              'Stop this job if an error occurs'.
    Step 6 — Click 'Run' → fill in job name in the Save Custom Job dialog.
    Step 7 — Click 'Start' in the Assessment Launcher dialog.
    Step 8 — Wait for the assessment to finish and assert the result passes.

Requirements:
    - Windows ADK (Windows Assessment Console / wac.exe) must be installed.
    - Install via: ChocoManager().install('windows-adk')
    - Must run on a supported Windows build (22000 / 22621 / 26100).
    - Requires administrator privileges.
    - BPFS requires Fast Startup to be enabled in Power settings.

Environment variables:
    ADK_BPFS_JOB_NAME    — Job name entered in the Save Custom Job dialog
                           (default: BPFS_Workflow_Test)
    ADK_BPFS_TIMEOUT     — Maximum seconds to wait for the assessment
                           (default: 7200 — 2 hours)
    ADK_LOG_DIR          — Override the base log directory for results

Run:
    pytest tests/integration/lib/testtool/test_windows_adk/test_bpfs_workflow.py -v -s
"""

import os
import time
import pytest
from pathlib import Path

from lib.testtool.windows_adk import ADKController


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bpfs_log_dir(tmp_path_factory) -> Path:
    """Per-session log directory for BPFS workflow results."""
    base = os.getenv("ADK_LOG_DIR")
    if base:
        log_dir = Path(base) / "bpfs_workflow"
    else:
        log_dir = tmp_path_factory.mktemp("bpfs_workflow")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_windows_adk
@pytest.mark.slow
class TestBPFSWorkflow:
    """
    End-to-end workflow test for Boot Performance (Fast Startup) via the
    Configure Job path in Windows Assessment Console.
    """

    def test_bpfs_configured_workflow(self, adk_env, check_environment, bpfs_log_dir):
        """
        Drive WAC through the full configured-job workflow:

            1. Open WAC → Run Individual Assessments → Boot performance (Fast Startup)
            2. Click Configure
            3. Settings: Use recommended = OFF, Iterations = 1, Wake timers = ON
            4. Overview: Stop this job if an error occurs = ON
            5. Run → Save Custom Job dialog → enter job name → OK
            6. Assessment Launcher → Start
            7. Wait for completion → assert result passes

        The test uses ADKController with assessment='bpfs_configured'.
        All UI automation is handled by UIRunner (pywinauto).
        """
        job_name = os.getenv("ADK_BPFS_JOB_NAME", "BPFS_Workflow_Test")
        timeout = int(os.getenv("ADK_BPFS_TIMEOUT", "7200"))

        ctrl = ADKController(config={"log_path": str(bpfs_log_dir)})
        ctrl.set_assessment(
            "bpfs_configured",
            num_iters=1,
            auto_boot=True,
            job_name=job_name,
        )

        ctrl.start()
        ctrl.join(timeout=timeout)

        passed, message = ctrl.get_result()
        assert passed, f"BPFS configured workflow failed: {message}"

    def test_bpfs_configured_result_files_exist(
        self, adk_env, check_environment, bpfs_log_dir
    ):
        """
        After running the BPFS configured workflow, verify that the expected
        result artefacts are present in the log directory:
            - At least one result sub-directory
            - AxeLog.txt inside the result sub-directory
            - JobInfo.log at the top level of the log directory

        This test depends on test_bpfs_configured_workflow running first and
        populating bpfs_log_dir; it is ordered accordingly via pytest-order
        or by natural declaration order.
        """
        # JobInfo.log written by UIRunner.read_job_info()
        job_info = bpfs_log_dir / "JobInfo.log"
        assert job_info.exists(), (
            f"JobInfo.log not found in log dir: {bpfs_log_dir}\n"
            "Ensure test_bpfs_configured_workflow ran successfully first."
        )

        # At least one result sub-directory must exist
        result_dirs = [p for p in bpfs_log_dir.iterdir() if p.is_dir()]
        assert result_dirs, (
            f"No result subdirectory found under {bpfs_log_dir}"
        )

        # AxeLog.txt must exist inside the first result directory
        axelog = result_dirs[0] / "AxeLog.txt"
        assert axelog.exists(), (
            f"AxeLog.txt not found in result directory: {result_dirs[0]}"
        )
