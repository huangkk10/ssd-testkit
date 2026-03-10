"""
RebootManager.reboot_cycles() — Real Reboot Integration Test

Performs 3 consecutive **real** system reboots within a single test step.
After each reboot Windows auto-starts pytest via the Startup BAT created by
RebootManager, the session resumes, test_01 is skipped (already completed),
test_02 increments its counter and either reboots again or continues.

Test Flow:
    Phase A (first run):
    1. test_01_precondition  — remove stale state, create log dirs
    2. test_02_reboot_cycles — reboot_cycles(3, ...): reboot #1 → os._exit(0)

    Phase B (after reboot 1):
    test_01 → SKIPPED (completed_tests)
    test_02 → reboot_cycles(3, ...): reboot #2 → os._exit(0)

    Phase C (after reboot 2):
    test_01 → SKIPPED
    test_02 → reboot_cycles(3, ...): reboot #3 → os._exit(0)

    Phase D (after reboot 3 — final recovery):
    test_01 → SKIPPED
    test_02 → reboot_cycles(3, ...): current==3 → return normally → PASS
    test_03_verify → assert reboot_count==3, state clean → PASS

Run on a real machine:
    pytest tests/integration/framework/test_reboot_cycles_real.py -v
"""

import sys
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.reboot_manager import RebootManager
from lib.logger import get_module_logger, logConfig, clear_log_files

logger = get_module_logger(__name__)

CYCLE_COUNT = 3


@pytest.mark.framework
@pytest.mark.reboot_cycles
@pytest.mark.slow
class TestRebootCyclesReal(BaseTestCase):
    """
    Real-reboot integration test for RebootManager.reboot_cycles().

    Inherits BaseTestCase so that:
    - setup_teardown_function (autouse) handles the skip-completed logic
      on every recovery boot.
    - mark_completed() is called automatically after each test body exits.
    """

    # ------------------------------------------------------------------
    # Fixture — overrides BaseTestCase.setup_teardown_class
    # ------------------------------------------------------------------

    @pytest.fixture(scope="class", autouse=True)
    def setup_test_class(self, request):
        """
        Minimal class-level setup — no RunCard, no Config.json.

        Sets cwd to this file's directory so that the relative state file
        path (./pytest_reboot_state.json) is stable across reboots.
        """
        cls = request.cls
        cls.original_cwd = os.getcwd()

        # ── Working directory + logging ────────────────────────────────
        test_dir = cls._setup_working_directory(__file__)

        # ── RebootManager ─────────────────────────────────────────────
        cls.reboot_mgr = RebootManager(total_tests=cls._count_test_methods())

        phase = "POST-REBOOT (recovering)" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
        logger.info(f"[SETUP] Phase       : {phase}")
        logger.info(f"[SETUP] reboot_count: {cls.reboot_mgr.state.get('reboot_count', 0)}")
        logger.info(f"[SETUP] completed   : {cls.reboot_mgr.state.get('completed_tests', [])}")
        logger.info(f"[SETUP] step_counts : {cls.reboot_mgr.state.get('step_reboot_counts', {})}")
        logger.info(f"[SETUP] Working dir : {test_dir}")

        yield

        # ── Teardown ──────────────────────────────────────────────────
        cls._teardown_reboot_manager()
        logger.info(f"{cls.__name__} session complete")
        os.chdir(cls.original_cwd)

    # ------------------------------------------------------------------
    # Phase A — Pre-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition — clean state")
    def test_01_precondition(self):
        """
        Remove any stale state file and log directory from a previous run,
        then create fresh log directories.

        This step runs ONLY on the very first boot.  All subsequent recovery
        boots skip it because it is in completed_tests.
        """
        logger.info("[TEST_01] Precondition started")

        # Remove stale reboot state file so the run starts clean
        state_file = Path(RebootManager.STATE_FILE)
        if state_file.exists():
            state_file.unlink()
            logger.info(f"[TEST_01] Removed stale state file: {state_file}")
            # Reload to get a fresh in-memory state after deletion
            self.reboot_mgr.state = self.reboot_mgr._load_state()

        # Create log directories
        for d in ["./testlog", "./log"]:
            Path(d).mkdir(parents=True, exist_ok=True)

        clear_log_files()
        logger.info("[TEST_01] Precondition complete")

    # ------------------------------------------------------------------
    # Phase B / C / D — Multi-reboot step
    # ------------------------------------------------------------------

    @pytest.mark.order(2)
    @step(2, f"Reboot cycles — {CYCLE_COUNT} times")
    def test_02_reboot_cycles(self, request):
        """
        Perform CYCLE_COUNT consecutive real system reboots.

        Each recovery:
        - test_01 is already in completed_tests → skipped automatically.
        - This step increments its per-step counter via reboot_cycles().
        - If counter < CYCLE_COUNT → schedules reboot → os._exit(0).
        - If counter == CYCLE_COUNT → returns normally.

        Execution past the reboot_cycles() call signals all reboots are done.
        """
        current = self.reboot_mgr._get_step_reboot_count(request.node.name)
        logger.info(
            f"[TEST_02] Entry — step reboot count: {current}/{CYCLE_COUNT}  "
            f"(global reboot_count={self.reboot_mgr.state.get('reboot_count', 0)})"
        )

        self.reboot_mgr.reboot_cycles(
            CYCLE_COUNT,
            request=request,
            test_file=__file__,
            delay=10,
            reason=f"reboot_cycles real test — cycle N/{CYCLE_COUNT}",
        )

        # Execution reaches here only after all CYCLE_COUNT reboots are done.
        logger.info(f"[TEST_02] All {CYCLE_COUNT} reboot(s) completed — continuing")

    # ------------------------------------------------------------------
    # Phase D — Verification (runs only after all reboots complete)
    # ------------------------------------------------------------------

    @pytest.mark.order(3)
    @step(3, "Verify reboot count and state")
    def test_03_verify(self):
        """
        Assert that the reboot cycle completed correctly:
        1. Global reboot_count == CYCLE_COUNT.
        2. test_02_reboot_cycles is in completed_tests.
        3. step_reboot_counts has no leftover entry for test_02.
        """
        logger.info("[TEST_03] Verification started")

        # 1. Global reboot count
        actual_rc = self.reboot_mgr.state.get("reboot_count", 0)
        assert actual_rc == CYCLE_COUNT, (
            f"reboot_count expected {CYCLE_COUNT}, got {actual_rc}"
        )
        logger.info(f"[TEST_03] reboot_count == {actual_rc} ✓")

        # 2. test_02 must be marked completed (by BaseTestCase teardown)
        assert self.reboot_mgr.is_completed("test_02_reboot_cycles"), (
            "test_02_reboot_cycles not found in completed_tests"
        )
        logger.info("[TEST_03] test_02_reboot_cycles in completed_tests ✓")

        # 3. step_reboot_counts must be clean
        leftover = self.reboot_mgr.state.get("step_reboot_counts", {})
        assert "test_02_reboot_cycles" not in leftover, (
            f"step_reboot_counts still has entry: {leftover}"
        )
        logger.info("[TEST_03] step_reboot_counts clean ✓")

        logger.info(f"[TEST_03] All verifications passed — {CYCLE_COUNT} reboots confirmed")
