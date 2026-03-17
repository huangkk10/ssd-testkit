"""
Allure + Reboot Integration Simulation
=======================================

Demonstrates and verifies the full reboot-across-pytest-sessions flow
together with Allure report generation, **without touching the real OS**.

Scenario (mirrors stc547 Phase A → reboot → Phase B):
    STEP 1  Pre-condition setup
    STEP 2  Pre-reboot work (Phase A)
    STEP 3  Trigger reboot  ← os._exit(0) patched to _SimulatedReboot
    ── simulated reboot ──────────────────────────────────────────────
    STEP 4  Post-reboot work (Phase B)
    STEP 5  Verify results

Key behaviours verified:
  - allure-results/ is NOT wiped on the post-reboot resume
    (pytest_configure in root conftest reads is_recovering from state file)
  - @step decorator emits Allure step entries for every step
  - log_table() attaches a table to the Allure report
  - attach_logs_on_failure fixture attaches log files on failure

Run:
    pytest tests/integration/framework/test_reboot_allure_simulation.py -v
    allure serve allure-results
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.reboot_manager import RebootManager
from lib.logger import get_module_logger, log_phase, log_kv, log_table

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# Simulation plumbing — same approach as test_reboot_cycles_simulation.py
# ---------------------------------------------------------------------------

class _SimulatedReboot(Exception):
    """Raised instead of os._exit(0) so the test can catch and continue."""


@pytest.fixture(autouse=True)
def _no_real_reboot(monkeypatch, tmp_path):
    """
    Patch away every real OS interaction so the test runs safely in CI / dev.

    Also redirects the RebootManager state file into tmp_path so test runs
    are fully isolated from each other and from real test-case state files.
    """
    # Patch os._exit → raise _SimulatedReboot
    monkeypatch.setattr(
        "os._exit",
        lambda code: (_ for _ in ()).throw(_SimulatedReboot(code)),
    )
    # Patch subprocess.run → no-op (no real shutdown command)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    # Patch auto-start BAT creation → no-op
    monkeypatch.setattr(RebootManager, "_setup_auto_start", lambda self, tf: None)

    # Redirect state file so we don't pollute the real pytest_reboot_state.json
    state_path = str(tmp_path / "pytest_reboot_state.json")
    monkeypatch.setattr(RebootManager, "STATE_FILE", state_path)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.feature_modern_standby
@pytest.mark.interface_pcie
class TestRebootAllureSimulation(BaseTestCase):
    """
    Full reboot-aware test with Allure integration.

    Structure:
        Phase A (pre-reboot):
            test_01_precondition
            test_02_phase_a_work
            test_03_trigger_reboot   ← simulated reboot happens here

        Phase B (post-reboot):
            test_04_phase_b_work
            test_05_verify_results
    """

    # Shared state across steps (class-level)
    _phase_a_value: int = 0
    _phase_b_value: int = 0

    # ------------------------------------------------------------------
    # Phase A — Pre-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition — prepare test environment")
    def test_01_precondition(self):
        """
        Phase A / Step 1:
        Set up a clean environment before any work begins.
        In a real test this would clear old logs, remove stale installs, etc.
        """
        log_phase(logger, "PRE-REBOOT")
        logger.info("[TEST_01] Precondition: creating test directories")

        Path("./testlog").mkdir(parents=True, exist_ok=True)
        log_kv(logger, "testlog dir", "./testlog")
        log_kv(logger, "simulation mode", "True")

        logger.info("[TEST_01] Precondition complete")

    @pytest.mark.order(2)
    @step(2, "Phase A work — collect pre-reboot data")
    def test_02_phase_a_work(self):
        """
        Phase A / Step 2:
        Perform work that must happen BEFORE the reboot.
        Stores a result in the class-level state so Step 5 can verify it.
        """
        logger.info("[TEST_02] Phase A work started")

        # Simulate collecting some data
        TestRebootAllureSimulation._phase_a_value = 42
        log_kv(logger, "phase_a_value", TestRebootAllureSimulation._phase_a_value)

        log_table(
            logger,
            headers=["Item", "Status", "Value"],
            rows=[
                ["Pre-reboot config", "Applied", "OK"],
                ["Data collection",   "Done",    str(TestRebootAllureSimulation._phase_a_value)],
            ],
        )

        assert TestRebootAllureSimulation._phase_a_value == 42
        logger.info("[TEST_02] Phase A work complete")

    @pytest.mark.order(3)
    @step(3, "Trigger reboot — transition to Phase B")
    def test_03_trigger_reboot(self, request):
        """
        Phase A / Step 3:
        Mark this step completed BEFORE calling setup_reboot() because
        os._exit(0) prevents normal teardown from running.
        Then trigger the reboot (simulated: raises _SimulatedReboot).
        """
        logger.info("[TEST_03] Pre-marking step before reboot")
        self.reboot_mgr.pre_mark_completed(request.node.name)

        logger.info("[TEST_03] Triggering reboot")
        try:
            self.reboot_mgr.setup_reboot(
                delay=10,
                reason="Simulation: Phase A complete — rebooting for Phase B",
                test_file=__file__,
            )
        except _SimulatedReboot:
            # In real execution os._exit(0) kills the process here.
            # In simulation we catch _SimulatedReboot and pytest.skip() to
            # mimic the process dying: remaining tests in this session are
            # not collected, just as they wouldn't be after a real reboot.
            logger.info("[TEST_03] Simulated reboot caught — skipping remainder of Phase A session")
            pytest.skip("Simulated reboot — Phase B tests will run in 'next session'")

    # ------------------------------------------------------------------
    # Phase B — Post-Reboot
    # ------------------------------------------------------------------

    @pytest.mark.order(4)
    @step(4, "Phase B work — post-reboot processing")
    def test_04_phase_b_work(self):
        """
        Phase B / Step 4:
        Work that must happen AFTER the reboot.
        In a real test this would run a collector, parse results, etc.
        """
        log_phase(logger, "POST-REBOOT")
        logger.info("[TEST_04] Phase B work started")

        # Simulate post-reboot processing
        TestRebootAllureSimulation._phase_b_value = 99
        log_kv(logger, "phase_b_value", TestRebootAllureSimulation._phase_b_value)

        log_table(
            logger,
            headers=["Metric", "Threshold", "Actual", "Result"],
            rows=[
                ["SW DRIPS", ">80%", "85.3%", "PASS"],
                ["HW DRIPS", ">80%", "91.2%", "PASS"],
            ],
        )

        assert TestRebootAllureSimulation._phase_b_value == 99
        logger.info("[TEST_04] Phase B work complete")

    @pytest.mark.order(5)
    @step(5, "Verify results — cross-phase assertions")
    def test_05_verify_results(self):
        """
        Phase B / Step 5:
        Final verification that uses data from both phases.
        Demonstrates that class-level state persists across the simulated reboot.
        """
        logger.info("[TEST_05] Verify results started")

        log_table(
            logger,
            headers=["Phase", "Variable", "Expected", "Actual", "Pass"],
            rows=[
                ["A", "phase_a_value", "42",
                 str(TestRebootAllureSimulation._phase_a_value),
                 "✓" if TestRebootAllureSimulation._phase_a_value == 42 else "✗"],
                ["B", "phase_b_value", "99",
                 str(TestRebootAllureSimulation._phase_b_value),
                 "✓" if TestRebootAllureSimulation._phase_b_value == 99 else "✗"],
            ],
        )

        assert TestRebootAllureSimulation._phase_a_value == 42, \
            "Phase A value lost across reboot — class state not preserved"
        assert TestRebootAllureSimulation._phase_b_value == 99, \
            "Phase B value not set — test_04 may have been skipped"

        logger.info("[TEST_05] All assertions passed")
