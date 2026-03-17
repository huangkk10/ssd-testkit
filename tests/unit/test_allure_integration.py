"""
Smoke tests for Allure report integration.

These tests verify that:
  1. @step decorator records steps in Allure (PASS / FAIL paths)
  2. log_table() renders correctly and attempts Allure attach
  3. log_phase() / allure_phase() write correctly
  4. Markers are present on the test item (mapped by conftest hook)

Run and view the report:
    pytest tests/unit/test_allure_integration.py -v
    allure serve allure-results
"""
import logging
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from framework.decorators import step
from lib.logger import get_module_logger, log_phase, log_kv, log_table, log_exception
from lib.allure_helper import allure_phase

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# Helper: a simple class that uses @step so we can call wrapper methods
# ---------------------------------------------------------------------------

class _StepHost:
    """Thin host so @step decorator (which reads func.__module__) works."""

    @step(1, "Passing step — basic arithmetic")
    def step_pass(self):
        assert 1 + 1 == 2

    @step(2, "Failing step — intentional assertion error")
    def step_fail(self):
        raise AssertionError("Intentional failure for Allure FAIL demo")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAllureIntegration:
    """Verify Allure integration helpers work end-to-end."""

    # ── @step decorator ──────────────────────────────────────────────────────

    def test_step_pass(self):
        """@step should complete without error on a passing function."""
        host = _StepHost()
        host.step_pass()   # must not raise

    def test_step_fail(self):
        """@step should re-raise the exception so pytest marks it FAILED.

        This test is *expected* to appear as FAILED in Allure — it demonstrates
        the FAIL path of the step decorator.
        """
        host = _StepHost()
        with pytest.raises(AssertionError, match="Intentional failure"):
            host.step_fail()

    # ── log helpers ──────────────────────────────────────────────────────────

    def test_log_phase(self):
        """log_phase() should write banner lines without raising."""
        log_phase(logger, "TEST-PHASE")

    def test_allure_phase(self):
        """allure_phase() should write banner + call allure.dynamic.feature (if available)."""
        allure_phase(logger, "ALLURE-PHASE")

    def test_log_kv(self):
        """log_kv() should format key-value pairs without raising."""
        log_kv(logger, "SW DRIPS", "85.3", "%")
        log_kv(logger, "HW DRIPS", "91.2", "%")

    def test_log_table(self):
        """log_table() should render ASCII table and attempt Allure attach."""
        log_table(
            logger,
            headers=["Session", "SW DRIPS", "HW DRIPS"],
            rows=[
                ["1", "85.3%", "91.2%"],
                ["2", "78.1%", "82.0%"],
            ],
        )

    def test_log_table_empty(self):
        """log_table() with no rows should be a no-op (no error)."""
        log_table(logger, headers=["A", "B"], rows=[])

    def test_log_exception(self):
        """log_exception() should capture exc info without re-raising."""
        try:
            raise ValueError("demo error")
        except ValueError as exc:
            log_exception(logger, "Caught demo error", exc,
                          context={"step": "test_log_exception", "value": 42})

    # ── Allure marker mapping (verified via conftest hook) ───────────────────

    @pytest.mark.feature_modern_standby
    @pytest.mark.interface_pcie
    def test_marker_mapping(self):
        """Markers on this test should appear as Feature/Tag in Allure Behaviors."""
        logger.info("[test_marker_mapping] markers applied — check Allure Behaviors page")

    # ── Allure attach_logs_on_failure fixture ────────────────────────────────

    def test_attach_logs_triggered_on_failure(self):
        """
        This test intentionally FAILS so the conftest autouse fixture
        ``attach_logs_on_failure`` will attach app.log / error.log to the
        Allure report.  Open the report and verify the Attachments tab.
        """
        logger.error("[ALLURE DEMO] This error should appear in error.log and be attached to Allure")
        pytest.fail("Intentional failure — check Allure Attachments tab for app.log / error.log")
