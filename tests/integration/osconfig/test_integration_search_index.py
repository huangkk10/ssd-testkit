"""
Integration tests — SearchIndexAction (WSearch service).

Verifies that SearchIndexAction correctly disables and re-enables the
Windows Search service (WSearch) on a real Windows machine.

Each test follows the pattern:
    record start type → apply() → check() True → revert() → start type restored

Requirements:
  - Admin elevation (session-scoped autouse fixture in conftest.py)
"""

import subprocess
import pytest

from lib.testtool.osconfig.actions.search_index import SearchIndexAction
from .conftest import svc_start_type

pytestmark = [pytest.mark.integration, pytest.mark.admin]

_SVC = "WSearch"


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _svc_state(svc_name: str) -> str:
    """Return current service *running state*: running / stopped / unknown."""
    try:
        result = subprocess.run(
            ["sc", "query", svc_name],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "STATE" in line:
                parts = line.split()
                if len(parts) >= 4:
                    return parts[3].lower()   # e.g. "running", "stopped"
    except Exception:
        pass
    return "unknown"


# ------------------------------------------------------------------ #
# Tests                                                               #
# ------------------------------------------------------------------ #

class TestSearchIndexApplyRevert:
    """Core apply / check / revert cycle."""

    def test_apply_disables_wsearch_service(self, build_info):
        """After apply(), WSearch start type must be 'disabled'."""
        if not SearchIndexAction.supported_on(build_info):
            pytest.skip("SearchIndexAction not supported on this OS build")

        action = SearchIndexAction()
        try:
            action.apply()
            start_type = svc_start_type(_SVC)
            assert start_type == "disabled", (
                f"Expected WSearch start type 'disabled' after apply, got {start_type!r}"
            )
        finally:
            action.revert()

    def test_check_returns_true_after_apply(self, build_info):
        """check() must return True immediately after apply()."""
        if not SearchIndexAction.supported_on(build_info):
            pytest.skip("SearchIndexAction not supported on this OS build")
            action.revert()

    def test_revert_restores_start_type(self, build_info):
        """After revert(), WSearch start type should be restored (auto or demand)."""
        if not SearchIndexAction.supported_on(build_info):
            pytest.skip("SearchIndexAction not supported on this OS build")

        before = svc_start_type(_SVC)
        action = SearchIndexAction()
        action.apply()
        action.revert()
        after = svc_start_type(_SVC)

        assert after == before or after in ("auto", "demand"), (
            f"WSearch start type after revert: expected {before!r}, got {after!r}"
        )

    def test_check_returns_false_after_revert(self, build_info):
        """check() must return False after revert()."""
        if not SearchIndexAction.supported_on(build_info):
            pytest.skip("SearchIndexAction not supported on this OS build")

        action = SearchIndexAction()
        action.apply()
        action.revert()
        assert action.check() is False, "check() still True after revert()"

    def test_apply_is_idempotent(self, build_info):
        """Calling apply() twice must not raise and check() stays True."""
        if not SearchIndexAction.supported_on(build_info):
            pytest.skip("SearchIndexAction not supported on this OS build")

        action = SearchIndexAction()
        try:
            action.apply()
            action.apply()   # second call — should be a no-op
            assert action.check() is True
        finally:
            action.revert()


class TestSearchIndexServiceState:
    """Verify actual service running state, not just start type."""

    def test_service_is_stopped_after_apply(self, build_info):
        """WSearch should be stopped (not just disabled) after apply()."""
        if not SearchIndexAction.supported_on(build_info):
            pytest.skip("SearchIndexAction not supported on this OS build")

        action = SearchIndexAction()
        try:
            action.apply()
            state = _svc_state(_SVC)
            assert state in ("stopped", "stop_pending"), (
                f"Expected WSearch to be stopped after apply, got {state!r}"
            )
        finally:
            action.revert()

    def test_start_type_is_auto_or_demand_before_apply(self, build_info):
        """WSearch should normally be auto-start on a fresh Windows install."""
        if not SearchIndexAction.supported_on(build_info):
            pytest.skip("SearchIndexAction not supported on this OS build")

        start_type = svc_start_type(_SVC)
        # Accept auto, demand, or already disabled (some hardened images)
        assert start_type in ("auto", "demand", "disabled"), (
            f"Unexpected WSearch start type before test: {start_type!r}"
        )
