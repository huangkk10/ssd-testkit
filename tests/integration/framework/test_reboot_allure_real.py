"""
Allure + Real Reboot Integration Test
======================================

Performs a **real** single system reboot mid-test and generates a complete
Allure report that covers both the pre-reboot and post-reboot phases.

Test Flow:
    Phase A — first pytest run (PRE-REBOOT):
        test_01  Precondition  — clean state, create dirs
        test_02  Phase A work  — verify pre-reboot environment
        test_03  Trigger reboot — setup_reboot() → os._exit(0)

    Phase B — resumed automatically after reboot (POST-REBOOT):
        test_01 → SKIPPED  (already in completed_tests)
        test_02 → SKIPPED
        test_03 → SKIPPED
        test_04  Phase B work  — verify post-reboot environment
        test_05  Final verify  — cross-phase assertions

After the run:
    allure serve allure-results

Prerequisites:
  - Run as Administrator (shutdown command requires elevated privileges)
  - The auto-start BAT in Windows Startup folder resumes pytest after reboot
  - Java 11+ and Allure CLI must be installed for report viewing

Run (first time only — reboot will happen automatically):
    pytest tests/integration/framework/test_reboot_allure_real.py -v --run-hardware
"""

import os
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.reboot_manager import RebootManager
from lib.logger import (
    get_module_logger,
    clear_log_files,
    log_phase,
    log_kv,
    log_table,
)

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.hardware
@pytest.mark.admin
@pytest.mark.integration
@pytest.mark.feature_power
@pytest.mark.slow
class TestRebootAllureReal(BaseTestCase):
    """
    Real-reboot test with full Allure report integration.

    Phase A (PRE-REBOOT):
        test_01  Precondition
        test_02  Pre-reboot work & verification
        test_03  Trigger real system reboot → auto-resume after boot

    Phase B (POST-REBOOT):
        test_04  Post-reboot work & verification
        test_05  Final cross-phase verification
    """

    # Class-level state shared between steps (survives within one session,
    # reset to default on post-reboot session — class body is re-executed).
    _pre_reboot_timestamp: str = ""
    _pre_reboot_hostname: str = ""

    # ------------------------------------------------------------------
    # Class fixture — minimal, no RunCard / Config.json needed
    # ------------------------------------------------------------------

    @pytest.fixture(scope="class", autouse=True)
    def setup_test_class(self, request):
        """
        Set working directory to this file's folder so the state file path
        (./pytest_reboot_state.json) is stable across reboots.
        """
        cls = request.cls
        cls.original_cwd = os.getcwd()

        test_dir = cls._setup_working_directory(__file__)
        cls.reboot_mgr = RebootManager(total_tests=cls._count_test_methods())

        phase = "POST-REBOOT" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
        log_phase(logger, phase)
        log_kv(logger, "reboot_count",
               cls.reboot_mgr.state.get("reboot_count", 0))
        log_kv(logger, "completed_tests",
               cls.reboot_mgr.state.get("completed_tests", []))
        logger.info(f"[SETUP] Working dir: {test_dir}")

        yield

        cls._teardown_reboot_manager()
        logger.info(f"{cls.__name__} session complete")
        os.chdir(cls.original_cwd)

    # ------------------------------------------------------------------
    # Phase A — Pre-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition — clean state and create log dirs")
    def test_01_precondition(self):
        """
        Remove stale state from previous runs and create fresh directories.
        Runs only on the very first boot; subsequent boots skip it automatically.
        """
        log_phase(logger, "PRE-REBOOT")
        logger.info("[TEST_01] Precondition started")

        # Remove stale reboot state so the run starts clean
        state_file = Path(RebootManager.STATE_FILE)
        if state_file.exists():
            state_file.unlink()
            logger.info(f"[TEST_01] Removed stale state: {state_file}")
            self.reboot_mgr.state = self.reboot_mgr._load_state()

        # Create required directories
        for d in ["./testlog", "./log"]:
            Path(d).mkdir(parents=True, exist_ok=True)
            log_kv(logger, "mkdir", d)

        clear_log_files()
        logger.info("[TEST_01] Precondition complete")

    @pytest.mark.order(2)
    @step(2, "Phase A work — collect pre-reboot environment info")
    def test_02_phase_a_work(self):
        """
        Record pre-reboot system information that will be compared post-reboot.
        In a real test this might install a tool, apply OS config, etc.
        """
        logger.info("[TEST_02] Phase A work started")

        import socket
        hostname = socket.gethostname()
        timestamp = datetime.now().isoformat(timespec="seconds")

        TestRebootAllureReal._pre_reboot_timestamp = timestamp
        TestRebootAllureReal._pre_reboot_hostname = hostname

        log_kv(logger, "hostname",  hostname)
        log_kv(logger, "timestamp", timestamp)
        log_kv(logger, "python",    sys.version.split()[0])
        log_kv(logger, "cwd",       os.getcwd())

        log_table(
            logger,
            headers=["Item", "Value", "Status"],
            rows=[
                ["Hostname",  hostname,                  "OK"],
                ["Timestamp", timestamp,                  "OK"],
                ["Python",    sys.version.split()[0],     "OK"],
                ["CWD",       str(Path.cwd().name),       "OK"],
            ],
        )

        assert hostname, "Could not resolve hostname"
        logger.info("[TEST_02] Phase A work complete")

    @pytest.mark.order(3)
    @step(3, "Trigger real system reboot — Phase A complete")
    def test_03_trigger_reboot(self, request):
        """
        Pre-mark this step completed BEFORE calling setup_reboot() because
        os._exit(0) prevents the normal BaseTestCase teardown from running.
        Then initiate the real system reboot (10-second delay).

        After reboot Windows auto-starts pytest via the Startup BAT.
        test_01, test_02, test_03 are skipped (already completed_tests).
        Execution resumes at test_04.
        """
        logger.info("[TEST_03] Pre-marking step before reboot")
        self.reboot_mgr.pre_mark_completed(request.node.name)

        logger.info("[TEST_03] Triggering real system reboot in 10 seconds...")
        self.reboot_mgr.setup_reboot(
            delay=10,
            reason="TestRebootAllureReal Phase A complete — rebooting for Phase B",
            test_file=__file__,
        )
        # os._exit(0) is called inside setup_reboot — code below never executes

    # ------------------------------------------------------------------
    # Phase B — Post-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(4)
    @step(4, "Phase B work — verify post-reboot environment")
    def test_04_phase_b_work(self):
        """
        Verify the system came back up correctly after the reboot.
        In a real test this might run a collector, parse results, check
        hardware state, etc.
        """
        log_phase(logger, "POST-REBOOT")
        logger.info("[TEST_04] Phase B work started")

        import socket
        post_hostname = socket.gethostname()
        post_timestamp = datetime.now().isoformat(timespec="seconds")
        reboot_count = self.reboot_mgr.state.get("reboot_count", 0)

        log_kv(logger, "post_hostname",  post_hostname)
        log_kv(logger, "post_timestamp", post_timestamp)
        log_kv(logger, "reboot_count",   reboot_count)

        log_table(
            logger,
            headers=["Check", "Result"],
            rows=[
                ["System online",   "PASS"],
                ["Python running",  "PASS"],
                ["reboot_count",    str(reboot_count)],
                ["Post hostname",   post_hostname],
            ],
        )

        assert reboot_count == 1, \
            f"Expected reboot_count=1 after one reboot, got {reboot_count}"
        assert post_hostname, "Could not resolve hostname post-reboot"
        logger.info("[TEST_04] Phase B work complete")

    @pytest.mark.order(5)
    @step(5, "Final verification — cross-phase assertions")
    def test_05_final_verify(self):
        """
        Final cross-phase verification.

        Note: _pre_reboot_timestamp and _pre_reboot_hostname are class-level
        defaults (empty strings) on the post-reboot session because the class
        body is re-executed fresh.  The meaningful assertion here is that the
        reboot count is correct and the system is healthy — not that in-memory
        values survived the reboot (they don't, by design; use a state file or
        log file for that).
        """
        logger.info("[TEST_05] Final verification started")

        reboot_count = self.reboot_mgr.state.get("reboot_count", 0)
        completed = self.reboot_mgr.state.get("completed_tests", [])

        log_table(
            logger,
            headers=["Assertion", "Expected", "Actual", "Pass"],
            rows=[
                ["reboot_count",
                 "1",
                 str(reboot_count),
                 "✓" if reboot_count == 1 else "✗"],
                ["test_03 completed",
                 "True",
                 str("test_03_trigger_reboot" in completed),
                 "✓" if "test_03_trigger_reboot" in completed else "✗"],
            ],
        )

        assert reboot_count == 1, \
            f"reboot_count expected 1, got {reboot_count}"
        assert "test_03_trigger_reboot" in completed, \
            "test_03_trigger_reboot not found in completed_tests — pre_mark failed?"

        logger.info("[TEST_05] All assertions passed ✓")
        logger.info("[TEST_05] Open Allure report: allure serve allure-results")
