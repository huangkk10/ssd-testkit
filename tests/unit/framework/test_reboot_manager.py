"""
Unit tests for framework.reboot_manager.RebootManager — reboot_cycles() API.

Strategy
--------
- Use tmp_path for the state file so tests are fully isolated.
- Patch os._exit with a side-effect that raises _ExitCalled so we can assert
  the call without the process actually dying.
- Patch subprocess.run and RebootManager._setup_auto_start to avoid real OS
  interactions (shutdown command, BAT file creation).
- Use a minimal FakeRequest stub in place of the pytest request fixture.
"""
import json
import sys
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Ensure project root is importable when running tests directly
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from framework.reboot_manager import RebootManager


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

class _ExitCalled(SystemExit):
    """Raised instead of os._exit(0) so tests can catch the call."""


def _make_request(name: str):
    """Minimal pytest request stub carrying node.name."""
    node = SimpleNamespace(name=name)
    return SimpleNamespace(node=node)


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #

@pytest.fixture
def mgr(tmp_path):
    """Fresh RebootManager backed by a tmp state file."""
    m = RebootManager(total_tests=5)
    m.state_file = str(tmp_path / "reboot_state.json")
    m.state = m._load_state()   # reload against new path
    return m


@pytest.fixture
def mock_reboot(monkeypatch):
    """
    Prevent real OS reboots:
    - os._exit  → raise _ExitCalled
    - subprocess.run → return success mock
    - RebootManager._setup_auto_start → no-op
    """
    monkeypatch.setattr("os._exit", lambda code: (_ for _ in ()).throw(_ExitCalled(code)))
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(RebootManager, "_setup_auto_start", lambda self, tf: None)


# ------------------------------------------------------------------ #
# TestRebootCycles                                                      #
# ------------------------------------------------------------------ #

class TestRebootCycles:

    def test_first_call_increments_count_and_exits(self, mgr, mock_reboot):
        """First reboot_cycles(3) call should increment counter to 1 and exit."""
        req = _make_request("test_02_stress_reboot")
        with pytest.raises(_ExitCalled):
            mgr.reboot_cycles(3, request=req, test_file=__file__)

        state = json.loads(Path(mgr.state_file).read_text())
        assert state["step_reboot_counts"]["test_02_stress_reboot"] == 1

    def test_does_not_mark_completed_before_last_cycle(self, mgr, mock_reboot):
        """Step must NOT appear in completed_tests while reboots are still pending."""
        req = _make_request("test_02_stress_reboot")
        with pytest.raises(_ExitCalled):
            mgr.reboot_cycles(3, request=req, test_file=__file__)

        state = json.loads(Path(mgr.state_file).read_text())
        assert "test_02_stress_reboot" not in state["completed_tests"]

    def test_second_call_increments_to_two(self, mgr, mock_reboot):
        """Simulate second recovery: counter should reach 2."""
        req = _make_request("test_02_stress_reboot")

        with pytest.raises(_ExitCalled):
            mgr.reboot_cycles(3, request=req, test_file=__file__)
        # Reload state as a fresh manager would after reboot
        mgr.state = mgr._load_state()

        with pytest.raises(_ExitCalled):
            mgr.reboot_cycles(3, request=req, test_file=__file__)

        state = json.loads(Path(mgr.state_file).read_text())
        assert state["step_reboot_counts"]["test_02_stress_reboot"] == 2

    def test_returns_normally_when_count_reached(self, mgr, mock_reboot):
        """After N reboots have been recorded, reboot_cycles must return (not exit)."""
        step = "test_02_stress_reboot"
        req = _make_request(step)

        # Simulate 3 prior reboots already in state
        mgr.state["step_reboot_counts"][step] = 3
        mgr._save_state()

        # Should NOT raise _ExitCalled
        mgr.reboot_cycles(3, request=req, test_file=__file__)  # must return

    def test_clears_step_count_on_completion(self, mgr, mock_reboot):
        """step_reboot_counts entry must be removed once reboot_cycles returns."""
        step = "test_02_stress_reboot"
        req = _make_request(step)

        mgr.state["step_reboot_counts"][step] = 3
        mgr._save_state()

        mgr.reboot_cycles(3, request=req, test_file=__file__)

        state = json.loads(Path(mgr.state_file).read_text())
        assert step not in state.get("step_reboot_counts", {})

    def test_global_reboot_count_increments_each_cycle(self, mgr, mock_reboot):
        """Global reboot_count must increase by 1 on every reboot."""
        req = _make_request("test_02_stress_reboot")

        assert mgr.state["reboot_count"] == 0
        with pytest.raises(_ExitCalled):
            mgr.reboot_cycles(3, request=req, test_file=__file__)

        state = json.loads(Path(mgr.state_file).read_text())
        assert state["reboot_count"] == 1

    def test_step_not_completed_mid_cycle(self, mgr, mock_reboot):
        """completed_tests must stay empty throughout all but the final cycle."""
        req = _make_request("test_02_stress_reboot")

        for _ in range(3):
            mgr.state = mgr._load_state()      # simulate fresh boot reload
            with pytest.raises(_ExitCalled):
                mgr.reboot_cycles(3, request=req, test_file=__file__)

        state = json.loads(Path(mgr.state_file).read_text())
        assert "test_02_stress_reboot" not in state["completed_tests"]


# ------------------------------------------------------------------ #
# TestBackwardCompat                                                    #
# ------------------------------------------------------------------ #

class TestBackwardCompat:

    def test_old_state_file_without_step_reboot_counts(self, tmp_path):
        """
        A state file written by the old RebootManager (no step_reboot_counts key)
        must load without error and behave correctly with reboot_cycles.
        """
        old_state = {
            "completed_tests": ["test_01_precondition"],
            "is_recovering": True,
            "current_test": None,
            "reboot_count": 1,
            # NO step_reboot_counts key
        }
        state_path = tmp_path / "reboot_state.json"
        state_path.write_text(json.dumps(old_state), encoding="utf-8")

        mgr = RebootManager(total_tests=5)
        mgr.state_file = str(state_path)
        mgr.state = mgr._load_state()

        assert mgr.state.get("step_reboot_counts") == {}
        assert mgr.is_completed("test_01_precondition")


# ------------------------------------------------------------------ #
# TestExistingAPIUnchanged                                              #
# ------------------------------------------------------------------ #

class TestExistingAPIUnchanged:

    def test_setup_reboot_still_increments_global_count(self, mgr, mock_reboot):
        """Existing setup_reboot() must still increment reboot_count."""
        assert mgr.state["reboot_count"] == 0
        with pytest.raises(_ExitCalled):
            mgr.setup_reboot(delay=0, reason="test", test_file=__file__)
        state = json.loads(Path(mgr.state_file).read_text())
        assert state["reboot_count"] == 1

    def test_pre_mark_completed_unchanged(self, mgr):
        """pre_mark_completed must still add step to completed_tests."""
        mgr.pre_mark_completed("test_05_clear_sleep_history")
        assert mgr.is_completed("test_05_clear_sleep_history")

    def test_require_after_fails_when_predecessor_missing(self, mgr):
        """require_after must still call pytest.fail when predecessor absent."""
        with pytest.raises(pytest.fail.Exception):
            mgr.require_after("test_09_clear_sleepstudy_and_reboot")


# ------------------------------------------------------------------ #
# TestLoopNext                                                          #
# ------------------------------------------------------------------ #

class TestLoopNext:

    STEPS = ["test_02_step_a", "test_03_step_b", "test_04_end_of_loop"]

    def _prime(self, mgr):
        """Mark loop steps as completed (simulates they ran in round 1)."""
        for s in self.STEPS:
            mgr.pre_mark_completed(s)
        mgr.state = mgr._load_state()   # reload from disk

    # ── reboot=True ────────────────────────────────────────────────

    def test_first_round_removes_steps_and_reboots(self, mgr, mock_reboot):
        """Non-final round: loop steps removed from completed_tests, os._exit called."""
        self._prime(mgr)
        with pytest.raises(_ExitCalled):
            mgr.loop_next("g", total=3, steps=self.STEPS, reboot=True, test_file=__file__)

        state = json.loads(Path(mgr.state_file).read_text())
        for s in self.STEPS:
            assert s not in state["completed_tests"], f"{s} should have been removed"
        assert state["loop_groups"]["g"]["current_round"] == 1

    def test_middle_round_increments_current_round(self, mgr, mock_reboot):
        """Second non-final round increments current_round to 2."""
        # Simulate state after round 1
        mgr.state["loop_groups"]["g"] = {"current_round": 1, "total_rounds": 3}
        mgr._save_state()
        self._prime(mgr)

        with pytest.raises(_ExitCalled):
            mgr.loop_next("g", total=3, steps=self.STEPS, reboot=True, test_file=__file__)

        state = json.loads(Path(mgr.state_file).read_text())
        assert state["loop_groups"]["g"]["current_round"] == 2

    def test_last_round_returns_and_cleans_group(self, mgr, mock_reboot):
        """Final round: returns normally and removes group from loop_groups."""
        mgr.state["loop_groups"]["g"] = {"current_round": 2, "total_rounds": 3}
        mgr._save_state()

        mgr.loop_next("g", total=3, steps=self.STEPS, reboot=True, test_file=__file__)

        state = json.loads(Path(mgr.state_file).read_text())
        assert "g" not in state.get("loop_groups", {})

    def test_preceding_step_not_removed(self, mgr, mock_reboot):
        """Steps outside the loop (e.g. test_01) must not be touched."""
        mgr.pre_mark_completed("test_01_precondition")
        self._prime(mgr)

        with pytest.raises(_ExitCalled):
            mgr.loop_next("g", total=3, steps=self.STEPS, reboot=True, test_file=__file__)

        state = json.loads(Path(mgr.state_file).read_text())
        assert "test_01_precondition" in state["completed_tests"]

    # ── reboot=False ───────────────────────────────────────────────

    def test_reboot_false_returns_without_exit(self, mgr, mock_reboot):
        """reboot=False: must return (never call os._exit) on non-final round."""
        self._prime(mgr)
        # Should NOT raise _ExitCalled
        mgr.loop_next("g", total=3, steps=self.STEPS, reboot=False)

    def test_reboot_false_removes_steps(self, mgr, mock_reboot):
        """reboot=False: loop steps still removed from completed_tests."""
        self._prime(mgr)
        mgr.loop_next("g", total=3, steps=self.STEPS, reboot=False)

        state = json.loads(Path(mgr.state_file).read_text())
        for s in self.STEPS:
            assert s not in state["completed_tests"]

    def test_reboot_false_last_round_cleans_group(self, mgr, mock_reboot):
        """reboot=False final round also removes the group entry."""
        mgr.state["loop_groups"]["g"] = {"current_round": 2, "total_rounds": 3}
        mgr._save_state()
        mgr.loop_next("g", total=3, steps=self.STEPS, reboot=False)

        state = json.loads(Path(mgr.state_file).read_text())
        assert "g" not in state.get("loop_groups", {})

    # ── multiple groups ────────────────────────────────────────────

    def test_multiple_groups_independent(self, mgr, mock_reboot):
        """Two groups must not interfere with each other."""
        steps_a = ["test_02_a"]
        steps_b = ["test_03_b"]
        mgr.pre_mark_completed("test_02_a")
        mgr.pre_mark_completed("test_03_b")
        mgr.state = mgr._load_state()

        # Advance group_a round 1/2 (non-final, total=2)
        with pytest.raises(_ExitCalled):
            mgr.loop_next("group_a", total=2, steps=steps_a, reboot=True, test_file=__file__)

        # After group_a advances: group_b must not exist yet, test_03_b still in completed_tests
        state = json.loads(Path(mgr.state_file).read_text())
        assert "group_b" not in state.get("loop_groups", {})
        assert "test_03_b" in state["completed_tests"]   # not part of group_a — must stay

        # Run group_b as a 1-round loop (single call → immediately final)
        mgr.state = mgr._load_state()
        mgr.pre_mark_completed("test_03_b")
        mgr.loop_next("group_b", total=1, steps=steps_b, reboot=False)

        state = json.loads(Path(mgr.state_file).read_text())
        assert "group_a" in state.get("loop_groups", {})    # group_a still alive at round 1
        assert "group_b" not in state.get("loop_groups", {})  # group_b done (1 round)

    # ── backward compatibility ─────────────────────────────────────

    def test_backward_compat_no_loop_groups_key(self, tmp_path):
        """Old state file without loop_groups loads cleanly."""
        old_state = {
            "completed_tests": ["test_01"],
            "is_recovering": False,
            "current_test": None,
            "reboot_count": 0,
            "step_reboot_counts": {},
            # NO loop_groups key
        }
        path = tmp_path / "state.json"
        path.write_text(json.dumps(old_state), encoding="utf-8")

        m = RebootManager(total_tests=5)
        m.state_file = str(path)
        m.state = m._load_state()

        assert m.state.get("loop_groups") == {}
