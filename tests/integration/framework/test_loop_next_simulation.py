"""
RebootManager.loop_next() — End-to-End Simulation Test
=======================================================

Simulates a multi-round test loop **within a single pytest session**
without touching the real OS.  This verifies the full loop_next()
state-machine logic — including inter-process state persistence that
survives real reboots — on any development machine.

Simulation model
----------------
A real N-round loop flow (total=3) looks like:

    Boot 1  — run loop steps, call loop_next() → [REBOOT]   (round 0 → 1)
    Boot 2  — run loop steps, call loop_next() → [REBOOT]   (round 1 → 2)
    Boot 3  — run loop steps, call loop_next() → return      (round 2 = final)
    Boot 3  — continue with post-loop tests

We emulate each "Boot" by:
  1. Reloading manager state from disk (as a fresh pytest session would)
  2. Simulating the loop-step test bodies (pre_mark_completed)
  3. Calling loop_next() — which either raises _SimulatedReboot or returns

Run with:
    pytest tests/integration/framework/test_loop_next_simulation.py -v
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from framework.reboot_manager import RebootManager


# ---------------------------------------------------------------------------
# Simulation plumbing
# ---------------------------------------------------------------------------

class _SimulatedReboot(Exception):
    """Raised in place of os._exit(0) to simulate a system reboot."""


def _make_request(step_name: str):
    """Minimal pytest request stub."""
    return SimpleNamespace(node=SimpleNamespace(name=step_name))


def _fresh_mgr(state_file: str, total_tests: int = 5) -> RebootManager:
    """Return a RebootManager that reloads state from *state_file* — just
    as a fresh pytest session does after a real reboot."""
    m = RebootManager(total_tests=total_tests)
    m.state_file = state_file
    m.state = m._load_state()
    return m


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state_file(tmp_path) -> str:
    return str(tmp_path / "reboot_state.json")


@pytest.fixture(autouse=True)
def _no_real_reboot(monkeypatch):
    """Replace real OS interactions with no-ops / exceptions."""
    monkeypatch.setattr(
        "os._exit",
        lambda code: (_ for _ in ()).throw(_SimulatedReboot(code)),
    )
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(RebootManager, "_setup_auto_start", lambda self, tf: None)


# ---------------------------------------------------------------------------
# Core simulation helper
# ---------------------------------------------------------------------------

def _simulate_one_round(
    state_file: str,
    group: str,
    steps: list,
    total: int,
    reboot: bool = True,
):
    """
    Simulate one pytest session / loop-round for the loop_next() state machine.

    Steps performed:
      1. Reload manager from disk (fresh session)
      2. Mark each loop step as "completed" (simulates test bodies running)
      3. Call loop_next() — raises _SimulatedReboot if non-final, or returns

    Returns:
        ("rebooted", state_dict)   — loop_next triggered a reboot
        ("completed", state_dict)  — loop_next returned (final round)
    """
    mgr = _fresh_mgr(state_file)

    # Simulate loop-step test bodies completing this round
    for step in steps:
        mgr.pre_mark_completed(step)

    try:
        mgr.loop_next(
            group,
            total=total,
            steps=steps,
            request=_make_request("test_loop_end"),
            test_file=__file__,
            reboot=reboot,
            delay=0,
        )
    except _SimulatedReboot:
        return "rebooted", json.loads(Path(state_file).read_text())

    return "completed", json.loads(Path(state_file).read_text())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoopNextSimulation:

    STEPS = ["test_02_loop_a", "test_03_loop_b"]
    GROUP = "main_loop"

    # ------------------------------------------------------------------
    # Round-sequence correctness
    # ------------------------------------------------------------------

    def test_3_round_loop_reboots_twice_then_completes(self, state_file):
        """
        total=3 must produce exactly 2 reboots (rounds 0→1, 1→2) and then
        complete on the third invocation (round 2 is final).
        """
        outcomes = []
        for _ in range(5):   # safety cap
            outcome, _ = _simulate_one_round(state_file, self.GROUP, self.STEPS, total=3)
            outcomes.append(outcome)
            if outcome == "completed":
                break

        assert outcomes == ["rebooted", "rebooted", "completed"], (
            f"Unexpected sequence: {outcomes}"
        )

    def test_single_round_loop_completes_immediately(self, state_file):
        """
        Edge case: total=1 means 'run loop body once without looping'.
        The very first call to loop_next must return (not reboot).
        """
        outcome, state = _simulate_one_round(
            state_file, self.GROUP, self.STEPS, total=1
        )
        assert outcome == "completed"
        assert self.GROUP not in state.get("loop_groups", {})

    def test_5_round_loop_reboots_four_times(self, state_file):
        """total=5 should produce 4 reboots then 1 completion."""
        outcomes = []
        for _ in range(7):
            outcome, _ = _simulate_one_round(state_file, self.GROUP, self.STEPS, total=5)
            outcomes.append(outcome)
            if outcome == "completed":
                break

        assert outcomes.count("rebooted") == 4
        assert outcomes[-1] == "completed"

    # ------------------------------------------------------------------
    # State correctness
    # ------------------------------------------------------------------

    def test_current_round_increments_each_boot(self, state_file):
        """loop_groups[group].current_round must increase by 1 per boot."""
        for expected_round in range(1, 3):   # after rounds 1 and 2 (non-final)
            _simulate_one_round(state_file, self.GROUP, self.STEPS, total=3)
            state = json.loads(Path(state_file).read_text())
            loop_groups = state.get("loop_groups", {})
            if self.GROUP in loop_groups:   # still alive (non-final)
                assert loop_groups[self.GROUP]["current_round"] == expected_round, (
                    f"Expected current_round={expected_round}, "
                    f"got {loop_groups[self.GROUP]['current_round']}"
                )

    def test_group_removed_after_final_round(self, state_file):
        """loop_groups entry must be completely absent after the final round."""
        for _ in range(4):
            outcome, state = _simulate_one_round(
                state_file, self.GROUP, self.STEPS, total=3
            )
            if outcome == "completed":
                break

        assert self.GROUP not in state.get("loop_groups", {}), (
            f"loop_groups not cleaned up: {state.get('loop_groups')}"
        )

    def test_steps_removed_from_completed_on_each_non_final_round(self, state_file):
        """After each non-final loop_next call, loop steps must be removed from
        completed_tests so they can run again on the next boot."""
        for _ in range(2):   # rounds 0 and 1 are non-final for total=3
            outcome, state = _simulate_one_round(
                state_file, self.GROUP, self.STEPS, total=3
            )
            if outcome == "rebooted":
                for step in self.STEPS:
                    assert step not in state["completed_tests"], (
                        f"{step} still in completed_tests after non-final reboot"
                    )

    def test_steps_remain_in_completed_after_final_round(self, state_file):
        """On the final loop round, loop_next returns without touching
        completed_tests — the steps remain as-is for the caller to manage."""
        for _ in range(4):
            outcome, state = _simulate_one_round(
                state_file, self.GROUP, self.STEPS, total=3
            )
            if outcome == "completed":
                # Steps were added by pre_mark_completed and NOT removed
                # because it's the final round
                for step in self.STEPS:
                    assert step in state["completed_tests"], (
                        f"{step} missing from completed_tests after final round"
                    )
                break

    def test_global_reboot_count_increments_per_reboot(self, state_file):
        """Global reboot_count must increase by 1 on every loop_next reboot."""
        expected = 0
        for _ in range(4):
            outcome, state = _simulate_one_round(
                state_file, self.GROUP, self.STEPS, total=3
            )
            if outcome == "rebooted":
                expected += 1
                assert state["reboot_count"] == expected, (
                    f"reboot_count expected {expected}, got {state['reboot_count']}"
                )

    # ------------------------------------------------------------------
    # Isolation / non-interference
    # ------------------------------------------------------------------

    def test_preceding_step_stays_completed(self, state_file):
        """A test completed before the loop must remain in completed_tests on
        every recovery boot (so BaseTestCase skips it correctly)."""
        # Simulate test_01 completing before the loop begins
        mgr = _fresh_mgr(state_file)
        mgr.mark_completed("test_01_precondition")

        for _ in range(4):
            outcome, state = _simulate_one_round(
                state_file, self.GROUP, self.STEPS, total=3
            )
            assert "test_01_precondition" in state["completed_tests"], (
                "test_01_precondition disappeared from completed_tests!"
            )
            if outcome == "completed":
                break

    def test_two_independent_groups_do_not_interfere(self, state_file):
        """Advancing one loop group must not affect another group's state."""
        steps_a = ["test_02_a"]
        steps_b = ["test_03_b"]

        # Run group_a one non-final round (total=2)
        outcome_a, state = _simulate_one_round(
            state_file, "group_a", steps_a, total=2
        )
        assert outcome_a == "rebooted"
        assert "group_b" not in state.get("loop_groups", {})  # group_b not touched

        # Now run group_b for a single complete round (total=1)
        outcome_b, state = _simulate_one_round(
            state_file, "group_b", steps_b, total=1
        )
        assert outcome_b == "completed"
        assert "group_a" in state.get("loop_groups", {})  # group_a still alive
        assert "group_b" not in state.get("loop_groups", {})  # group_b done

    # ------------------------------------------------------------------
    # reboot=False (no-reboot) mode
    # ------------------------------------------------------------------

    def test_reboot_false_multiple_rounds_inline(self, state_file):
        """
        With reboot=False all rounds complete inside a single process without
        any exception being raised.  The call is idempotent and only removes
        steps on non-final rounds; the group is cleaned up on the final call.
        """
        outcomes = []
        for _ in range(4):
            outcome, state = _simulate_one_round(
                state_file, self.GROUP, self.STEPS, total=3, reboot=False
            )
            outcomes.append(outcome)
            # Every round must complete without reboot, even non-final ones
            assert outcome == "completed", (
                "loop_next(reboot=False) must never raise (no reboot)"
            )
            # After we've gone through all rounds, group must be gone
            if len(outcomes) >= 3:
                assert self.GROUP not in state.get("loop_groups", {})
                break

    def test_reboot_false_removes_steps_on_non_final_rounds(self, state_file):
        """
        Even with reboot=False, non-final rounds must remove steps from
        completed_tests (so callers can re-run them if desired).
        """
        # Round 1 of 2 (non-final)
        outcome, state = _simulate_one_round(
            state_file, self.GROUP, self.STEPS, total=2, reboot=False
        )
        assert outcome == "completed"   # no reboot raised
        for step in self.STEPS:
            assert step not in state["completed_tests"], (
                f"{step} NOT removed from completed_tests on non-final reboot=False round"
            )
