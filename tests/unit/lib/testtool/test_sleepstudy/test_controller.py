"""
Unit tests for lib.testtool.sleepstudy.controller.SleepStudyController
"""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lib.testtool.sleepstudy.controller import SleepStudyController
from lib.testtool.sleepstudy.exceptions import SleepStudyConfigError, SleepStudyProcessError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ctrl(tmp_path) -> SleepStudyController:
    """Controller with output in a temp directory."""
    return SleepStudyController(
        output_path=str(tmp_path / "report.html"),
        timeout=30,
    )


@pytest.fixture(autouse=True)
def patch_subprocess(tmp_path):
    """
    Patch subprocess.run to simulate a successful powercfg run.
    Also creates the expected output file so the controller sees it.
    """
    report = tmp_path / "report.html"

    def _fake_run(cmd, **kwargs):
        # Write a minimal report file so controller considers it success
        report.write_text("<html></html>", encoding="utf-8")
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("lib.testtool.sleepstudy.controller.subprocess.run", side_effect=_fake_run):
        yield


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestControllerInit:
    def test_status_none_before_start(self, ctrl):
        assert ctrl.status is None

    def test_error_message_none_before_start(self, ctrl):
        assert ctrl.error_message is None

    def test_output_path_resolved(self, tmp_path):
        c = SleepStudyController(output_path=str(tmp_path / "r.html"))
        assert c.output_path.is_absolute()

    def test_invalid_timeout_raises(self, tmp_path):
        with pytest.raises(SleepStudyConfigError):
            SleepStudyController(output_path=str(tmp_path / "r.html"), timeout=-1)

    def test_is_daemon_thread(self, ctrl):
        assert ctrl.daemon is True


# ---------------------------------------------------------------------------
# Successful run
# ---------------------------------------------------------------------------

class TestControllerRun:
    def test_status_true_on_success(self, ctrl):
        ctrl.start()
        ctrl.join(timeout=5)
        assert ctrl.status is True

    def test_error_message_none_on_success(self, ctrl):
        ctrl.start()
        ctrl.join(timeout=5)
        assert ctrl.error_message is None

    def test_output_file_exists_after_run(self, ctrl):
        ctrl.start()
        ctrl.join(timeout=5)
        assert ctrl.output_path.exists()


# ---------------------------------------------------------------------------
# get_parser
# ---------------------------------------------------------------------------

class TestGetParser:
    def test_get_parser_returns_sleep_report_parser(self, ctrl, tmp_path):
        ctrl.start()
        ctrl.join(timeout=5)
        from lib.testtool.sleepstudy.sleep_report_parser import SleepReportParser
        parser = ctrl.get_parser()
        assert isinstance(parser, SleepReportParser)

    def test_get_parser_raises_if_no_report(self, tmp_path):
        ctrl = SleepStudyController(output_path=str(tmp_path / "missing.html"), timeout=30)
        # Do NOT run the controller — no report file exists
        with pytest.raises(SleepStudyProcessError, match="not found"):
            ctrl.get_parser()


# ---------------------------------------------------------------------------
# Error paths (mocked failures)
# ---------------------------------------------------------------------------

class TestControllerFailurePaths:
    def test_status_false_on_nonzero_exit(self, tmp_path):
        c = SleepStudyController(output_path=str(tmp_path / "r.html"), timeout=30)
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "Access denied"
        with patch(
            "lib.testtool.sleepstudy.controller.subprocess.run",
            return_value=fail_result,
        ):
            c.start()
            c.join(timeout=5)
        assert c.status is False
        assert "exited with code 1" in c.error_message

    def test_status_false_on_timeout(self, tmp_path):
        c = SleepStudyController(output_path=str(tmp_path / "r.html"), timeout=1)
        with patch(
            "lib.testtool.sleepstudy.controller.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="powercfg", timeout=1),
        ):
            c.start()
            c.join(timeout=5)
        assert c.status is False
        assert "timed out" in c.error_message

    def test_status_false_on_file_not_found_exe(self, tmp_path):
        c = SleepStudyController(output_path=str(tmp_path / "r.html"), timeout=30)
        with patch(
            "lib.testtool.sleepstudy.controller.subprocess.run",
            side_effect=FileNotFoundError("powercfg.exe"),
        ):
            c.start()
            c.join(timeout=5)
        assert c.status is False
        assert "not found" in c.error_message

    def test_status_false_when_report_not_produced(self, tmp_path):
        """powercfg exits 0 but doesn't write the HTML — controller should fail."""
        c = SleepStudyController(output_path=str(tmp_path / "r.html"), timeout=30)
        ok_result = MagicMock()
        ok_result.returncode = 0
        ok_result.stderr = ""
        # Note: does NOT write the output file
        with patch(
            "lib.testtool.sleepstudy.controller.subprocess.run",
            return_value=ok_result,
        ):
            c.start()
            c.join(timeout=5)
        assert c.status is False
        assert "not produced" in c.error_message
