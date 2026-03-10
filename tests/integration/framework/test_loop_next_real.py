"""
RebootManager.loop_next() — Real Reboot Integration Test

Validates that a block of test steps (test_02 ~ test_04) can be repeated
N full rounds via loop_next(reboot=True), with real system reboots between
rounds.  After all rounds complete, test_05 executes as the post-loop step.

Test Flow  (total=3 → 2 reboots)
---------------------------------
Boot 1 — PRE-REBOOT:
  test_01 ✓  precondition (state cleanup)
  test_02 ✓  loop step A
  test_03 ✓  loop step B
  test_04 ✓  loop end → loop_next: round 0→1, remove test_02/03/04, REBOOT

Boot 2 — POST-REBOOT 1  (reboot_count=1):
  test_01 → skip (completed_tests) ✓
  test_02 ✓  (re-runs because removed from completed_tests)
  test_03 ✓  (re-runs)
  test_04 ✓  → loop_next: round 1→2, remove, REBOOT

Boot 3 — POST-REBOOT 2  (reboot_count=2):
  test_01 → skip ✓
  test_02 ✓  (re-runs)
  test_03 ✓  (re-runs)
  test_04 ✓  → loop_next: round 2 == total-1 → return normally
  test_05 ✓  verify: reboot_count==2, loop_groups clean, all rounds logged

Run on a real machine:
    pytest tests/integration/framework/test_loop_next_real.py -v
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

# Total loop rounds.  Produces (TOTAL_ROUNDS - 1) real reboots.
TOTAL_ROUNDS = 3
EXPECTED_REBOOTS = TOTAL_ROUNDS - 1   # = 2

# Names that form the loop block — must match the actual method names below.
_LOOP_STEPS = [
    "test_02_loop_step_a",
    "test_03_loop_step_b",
    "test_04_loop_end",
]
_LOOP_GROUP = "main_loop"


@pytest.mark.framework
@pytest.mark.loop_next
@pytest.mark.slow
class TestLoopNextReal(BaseTestCase):
    """
    Real-reboot integration test for RebootManager.loop_next().

    Inherits BaseTestCase so that:
    - setup_teardown_function (autouse) handles the skip-completed logic
      on every recovery boot automatically.
    - mark_completed() is called for each step after its body exits.
    """

    # ------------------------------------------------------------------
    # Fixture — minimal class setup (no RunCard / Config.json needed)
    # ------------------------------------------------------------------

    @pytest.fixture(scope="class", autouse=True)
    def setup_test_class(self, request):
        """
        Set cwd to this file's directory so the relative state file path
        (./pytest_reboot_state.json) is stable across reboots.
        """
        cls = request.cls
        cls.original_cwd = os.getcwd()

        test_dir = cls._setup_working_directory(__file__)

        cls.reboot_mgr = RebootManager(total_tests=cls._count_test_methods())

        phase = "POST-REBOOT (recovering)" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
        groups = cls.reboot_mgr.state.get("loop_groups", {})
        current = groups.get(_LOOP_GROUP, {}).get("current_round", 0)

        logger.info(f"[SETUP] Phase        : {phase}")
        logger.info(f"[SETUP] reboot_count : {cls.reboot_mgr.state.get('reboot_count', 0)}")
        logger.info(f"[SETUP] loop round   : {current}/{TOTAL_ROUNDS}")
        logger.info(f"[SETUP] completed    : {cls.reboot_mgr.state.get('completed_tests', [])}")
        logger.info(f"[SETUP] Working dir  : {test_dir}")

        yield

        cls._teardown_reboot_manager()
        logger.info(f"{cls.__name__} session complete")
        os.chdir(cls.original_cwd)

    # ------------------------------------------------------------------
    # test_01 — Precondition (runs only on the very first boot)
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition — clean state")
    def test_01_precondition(self):
        """
        Remove stale state file and log directories from previous runs.
        Skipped on every recovery boot (present in completed_tests).
        """
        logger.info("[TEST_01] Precondition started")

        state_file = Path(RebootManager.STATE_FILE)
        if state_file.exists():
            state_file.unlink()
            logger.info(f"[TEST_01] Removed stale state file: {state_file}")
            self.reboot_mgr.state = self.reboot_mgr._load_state()

        for d in ["./testlog", "./log"]:
            Path(d).mkdir(parents=True, exist_ok=True)

        clear_log_files()
        logger.info("[TEST_01] Precondition complete")

    # ------------------------------------------------------------------
    # Loop block: test_02 ~ test_04  (repeated TOTAL_ROUNDS times)
    # ------------------------------------------------------------------

    @pytest.mark.order(2)
    @step(2, "Loop step A")
    def test_02_loop_step_a(self):
        """
        First step of the loop block.
        Runs on every round; skipped only when NOT in the loop block.
        """
        groups = self.reboot_mgr.state.get("loop_groups", {})
        current_round = groups.get(_LOOP_GROUP, {}).get("current_round", 0)
        logger.info(
            f"[TEST_02] Loop step A — round {current_round + 1}/{TOTAL_ROUNDS} "
            f"(reboot_count={self.reboot_mgr.state.get('reboot_count', 0)})"
        )

    @pytest.mark.order(3)
    @step(3, "Loop step B")
    def test_03_loop_step_b(self):
        """
        Second step of the loop block.
        Runs on every round; skipped only when NOT in the loop block.
        """
        groups = self.reboot_mgr.state.get("loop_groups", {})
        current_round = groups.get(_LOOP_GROUP, {}).get("current_round", 0)
        logger.info(
            f"[TEST_03] Loop step B — round {current_round + 1}/{TOTAL_ROUNDS}"
        )

    @pytest.mark.order(4)
    @step(4, f"Loop end — {TOTAL_ROUNDS} rounds with reboot")
    def test_04_loop_end(self, request):
        """
        Last step of the loop block.  Calls loop_next() to decide whether to
        reboot (non-final round) or continue to test_05 (final round).

        Non-final rounds:
          - test_02/03/04 removed from completed_tests
          - real system reboot scheduled → os._exit(0)

        Final round (round index == TOTAL_ROUNDS - 1):
          - loop_groups["main_loop"] cleaned up
          - method returns normally → test_05 executes next
        """
        groups = self.reboot_mgr.state.get("loop_groups", {})
        current_round = groups.get(_LOOP_GROUP, {}).get("current_round", 0)
        logger.info(
            f"[TEST_04] Loop end — round {current_round + 1}/{TOTAL_ROUNDS}, "
            f"calling loop_next(total={TOTAL_ROUNDS}, reboot=True)"
        )

        self.reboot_mgr.loop_next(
            _LOOP_GROUP,
            total=TOTAL_ROUNDS,
            steps=_LOOP_STEPS,
            request=request,
            test_file=__file__,
            reboot=True,
            delay=10,
            reason=f"loop_next real test — round N/{TOTAL_ROUNDS}",
        )

        # Reached here only on the final round.
        logger.info(f"[TEST_04] All {TOTAL_ROUNDS} rounds completed — loop_next returned")

    # ------------------------------------------------------------------
    # test_05 — Post-loop verification (runs after all rounds complete)
    # ------------------------------------------------------------------

    @pytest.mark.order(5)
    @step(5, "Verify loop completion")
    def test_05_verify(self):
        """
        Assert post-loop invariants after all TOTAL_ROUNDS have finished:

        1. Global reboot_count == EXPECTED_REBOOTS (== TOTAL_ROUNDS - 1).
        2. loop_groups has no entry for _LOOP_GROUP (cleaned up by loop_next).
        3. test_01_precondition is still in completed_tests (never removed).
        4. Each loop step (test_02/03/04) is in completed_tests
           (marked by BaseTestCase teardown after the final round).
        """
        logger.info("[TEST_05] Verification started")

        # 1. Global reboot count
        actual_rc = self.reboot_mgr.state.get("reboot_count", 0)
        assert actual_rc == EXPECTED_REBOOTS, (
            f"reboot_count expected {EXPECTED_REBOOTS}, got {actual_rc}"
        )
        logger.info(f"[TEST_05] reboot_count == {actual_rc} ✓")

        # 2. loop_groups entry must be gone
        leftover_groups = self.reboot_mgr.state.get("loop_groups", {})
        assert _LOOP_GROUP not in leftover_groups, (
            f"loop_groups still has entry for '{_LOOP_GROUP}': {leftover_groups}"
        )
        logger.info(f"[TEST_05] loop_groups['{_LOOP_GROUP}'] cleaned up ✓")

        # 3. Preceding step (test_01) must still be completed
        assert self.reboot_mgr.is_completed("test_01_precondition"), (
            "test_01_precondition disappeared from completed_tests"
        )
        logger.info("[TEST_05] test_01_precondition still completed ✓")

        # 4. All loop steps must be in completed_tests (final round teardown)
        for step_name in _LOOP_STEPS:
            assert self.reboot_mgr.is_completed(step_name), (
                f"{step_name} not found in completed_tests after final round"
            )
            logger.info(f"[TEST_05] {step_name} in completed_tests ✓")

        logger.info(
            f"[TEST_05] All verifications passed — "
            f"{TOTAL_ROUNDS} rounds, {EXPECTED_REBOOTS} reboots confirmed"
        )
