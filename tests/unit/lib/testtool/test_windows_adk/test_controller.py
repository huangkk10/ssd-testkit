"""
Unit tests for windows_adk ADKController.

pywinauto, subprocess, and platform are fully mocked.
"""

import subprocess
import pytest
from unittest.mock import MagicMock, patch

from lib.testtool.windows_adk.controller import ADKController
from lib.testtool.windows_adk.exceptions import ADKError


# Helper to create a controller patched to a specific build number
def _make_controller(build: int = 26100, extra_config: dict = None):
    config = extra_config or {}
    with patch(
        "lib.testtool.windows_adk.controller.get_build_number",
        return_value=build,
    ):
        return ADKController(config=config)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_detects_build_number_26100(self):
        ctrl = _make_controller(26100)
        assert ctrl._build == 26100

    def test_init_detects_build_number_22621(self):
        ctrl = _make_controller(22621)
        assert ctrl._build == 22621

    def test_init_default_result_not_run(self):
        ctrl = _make_controller()
        ok, msg = ctrl.get_result()
        assert ok is False
        assert "Not run" in msg

    def test_init_unsupported_build_raises(self):
        with pytest.raises(ADKError):
            _make_controller(build=19041)


# ---------------------------------------------------------------------------
# set_assessment
# ---------------------------------------------------------------------------

class TestSetAssessment:
    def test_set_valid_assessment(self):
        ctrl = _make_controller()
        ctrl.set_assessment("bpfs")
        assert ctrl._assessment_name == "bpfs"

    def test_set_bpfs_num_iters_with_kwargs(self):
        ctrl = _make_controller()
        ctrl.set_assessment("bpfs_num_iters", num_iters=5, auto_boot=False)
        assert ctrl._assessment_name == "bpfs_num_iters"
        assert ctrl._assessment_kwargs["num_iters"] == 5

    def test_set_unknown_assessment_raises(self):
        ctrl = _make_controller()
        with pytest.raises(ADKError, match="Unknown assessment"):
            ctrl.set_assessment("unknown_test")


# ---------------------------------------------------------------------------
# get_power_state
# ---------------------------------------------------------------------------

class TestGetPowerState:
    def test_s3_detected(self):
        ctrl = _make_controller()
        with patch("subprocess.check_output", return_value=b"    Standby (S3)\n"):
            state = ctrl.get_power_state()
        assert state == "S3"

    def test_cs_detected(self):
        ctrl = _make_controller()
        with patch("subprocess.check_output", return_value=b"    Standby (S0 Low Power Idle) Network Connected\n"):
            state = ctrl.get_power_state()
        assert state == "CS"

    def test_unknown_when_no_match(self):
        ctrl = _make_controller()
        with patch("subprocess.check_output", return_value=b"nothing useful\n"):
            state = ctrl.get_power_state()
        assert state == "Unknown"

    def test_unknown_on_subprocess_error(self):
        ctrl = _make_controller()
        with patch("subprocess.check_output", side_effect=Exception("fail")):
            state = ctrl.get_power_state()
        assert state == "Unknown"


# ---------------------------------------------------------------------------
# cleanup_dirs
# ---------------------------------------------------------------------------

class TestCleanupDirs:
    def test_creates_dirs_after_removal(self, temp_dir):
        ctrl = _make_controller(extra_config={"log_path": temp_dir})
        with patch.object(ctrl._adapter, "get_result_dir", return_value=f"{temp_dir}\\result"):
            with patch.object(ctrl._adapter, "get_job_dir",    return_value=f"{temp_dir}\\jobs"):
                with patch.object(ctrl._adapter, "get_test_dir",   return_value=f"{temp_dir}\\test"):
                    ctrl.cleanup_dirs()
        import os
        assert os.path.isdir(f"{temp_dir}\\result")
        assert os.path.isdir(f"{temp_dir}\\jobs")
        assert os.path.isdir(f"{temp_dir}\\test")
