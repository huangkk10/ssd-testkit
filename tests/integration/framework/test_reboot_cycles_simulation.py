"""
RebootManager.reboot_cycles() — End-to-End Simulation Test
===========================================================

Simulates multiple consecutive reboots **within a single pytest session**
without touching the real OS.  This lets you verify the full reboot_cycles()
state-machine logic — including the inter-process state persistence that
survives real reboots — on any development machine.

Simulation model
----------------
A real multi-reboot flow looks like:
    pytest run 1  →  reboot_cycles() → os._exit(0)  →  [REBOOT]
    pytest run 2  →  reboot_cycles() → os._exit(0)  →  [REBOOT]
    pytest run 3  →  reboot_cycles() → return        →  test body continues

We emulate this by patching os._exit to raise _SimulatedReboot, catching the
exception in a helper, then *reloading* the state file from disk before the
next "run" — exactly what a fresh pytest session would do after a real reboot.

Run with:
    pytest tests/integration/test_reboot_cycles_simulation.py -v
"""

import json
import sys
import os
import subprocess
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


def _fresh_mgr(state_file: str, total_tests: int = 3) -> RebootManager:
    """Return a RebootManager that reloads state from *state_file* — as a
    fresh pytest session would do on boot."""
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
# Helpers that mirror what BaseTestCase + test body do each "boot"
# ---------------------------------------------------------------------------

def _simulate_one_boot(state_file: str, step_name: str, cycle_count: int):
    """
    Simulate one pytest session boot for the multi-reboot step.

    Returns:
        ("rebooted", reboot_count)  — reboot_cycles triggered a reboot
        ("completed", reboot_count) — reboot_cycles returned normally
    """
    mgr = _fresh_mgr(state_file)

    try:
        mgr.reboot_cycles(cycle_count, request=_make_request(step_name), test_file=__file__)
    except _SimulatedReboot:
        # Mirrors setup_reboot behaviour: reboot_count already incremented
        # and state persisted inside setup_reboot before os._exit.
        return "rebooted", mgr._load_state()["reboot_count"]

    # reboot_cycles returned — all N reboots done.
    # Mirrors BaseTestCase.setup_teardown_function teardown: mark_completed.
    mgr.mark_completed(step_name)
    final_state = mgr._load_state()
    return "completed", final_state["reboot_count"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRebootCyclesSimulation:

    def test_exact_cycle_count_reboots_then_completes(self, state_file):
        """
        Full end-to-end: reboot_cycles(3) should reboot exactly 3 times and
        then return on the 4th invocation (3 reboots done → continue).
        """
        step = "test_02_reboot_cycles"
        CYCLES = 3

        outcomes = []
        for boot_number in range(1, CYCLES + 2):   # up to N+1 boots
            outcome, rb_count = _simulate_one_boot(state_file, step, CYCLES)
            outcomes.append(outcome)
            if outcome == "completed":
                break

        # Exactly 3 reboots, then 1 completion
        assert outcomes == ["rebooted"] * CYCLES + ["completed"], (
            f"Unexpected outcome sequence: {outcomes}"
        )
        assert rb_count == CYCLES

    def test_reboot_count_increments_each_boot(self, state_file):
        """Global reboot_count must increase by 1 on every simulated reboot."""
        step = "test_02_reboot_cycles"
        expected_rb = 0

        for _ in range(3):
            outcome, rb_count = _simulate_one_boot(state_file, step, 3)
            if outcome == "rebooted":
                expected_rb += 1
                assert rb_count == expected_rb, (
                    f"reboot_count expected {expected_rb}, got {rb_count}"
                )

    def test_step_not_in_completed_during_reboots(self, state_file):
        """
        The multi-reboot step must NOT appear in completed_tests while reboots
        are still pending (otherwise it would be skipped on recovery).
        """
        step = "test_02_reboot_cycles"

        for _ in range(3):
            _simulate_one_boot(state_file, step, 3)
            state = json.loads(Path(state_file).read_text())
            if state.get("step_reboot_counts", {}).get(step, 0) < 3:
                assert step not in state["completed_tests"], (
                    "Step marked completed prematurely!"
                )

    def test_step_completed_after_last_reboot(self, state_file):
        """After all reboots + return, step must be in completed_tests."""
        step = "test_02_reboot_cycles"

        for _ in range(4):   # 3 reboots + 1 completion
            outcome, _ = _simulate_one_boot(state_file, step, 3)
            if outcome == "completed":
                break

        state = json.loads(Path(state_file).read_text())
        assert step in state["completed_tests"]

    def test_step_reboot_counts_cleared_after_completion(self, state_file):
        """step_reboot_counts entry must be absent once the step is done."""
        step = "test_02_reboot_cycles"

        for _ in range(4):
            outcome, _ = _simulate_one_boot(state_file, step, 3)
            if outcome == "completed":
                break

        state = json.loads(Path(state_file).read_text())
        assert step not in state.get("step_reboot_counts", {}), (
            f"step_reboot_counts not cleaned up: {state.get('step_reboot_counts')}"
        )

    def test_preceding_step_skipped_on_recovery(self, state_file):
        """
        A step that was completed before reboot_cycles must be in
        completed_tests on every recovery boot (and would be skipped by
        BaseTestCase.setup_teardown_function).
        """
        step = "test_02_reboot_cycles"

        # Simulate test_01 completing before the reboot loop
        mgr = _fresh_mgr(state_file)
        mgr.mark_completed("test_01_precondition")

        for _ in range(4):
            outcome, _ = _simulate_one_boot(state_file, step, 3)
            # On every boot (including mid-cycle), test_01 must stay completed
            state = json.loads(Path(state_file).read_text())
            assert "test_01_precondition" in state["completed_tests"], (
                "test_01 disappeared from completed_tests!"
            )
            if outcome == "completed":
                break

    def test_configurable_cycle_count(self, state_file):
        """reboot_cycles(N) should work for any N (tested with N=5)."""
        step = "test_02_reboot_cycles"
        CYCLES = 5

        outcomes = []
        for _ in range(CYCLES + 2):
            outcome, _ = _simulate_one_boot(state_file, step, CYCLES)
            outcomes.append(outcome)
            if outcome == "completed":
                break

        assert outcomes.count("rebooted") == CYCLES
        assert outcomes[-1] == "completed"

    def test_single_cycle(self, state_file):
        """Edge case: reboot_cycles(1) should reboot once then complete."""
        step = "test_02_reboot_cycles"

        outcome1, _ = _simulate_one_boot(state_file, step, 1)
        outcome2, _ = _simulate_one_boot(state_file, step, 1)

        assert outcome1 == "rebooted"
        assert outcome2 == "completed"
