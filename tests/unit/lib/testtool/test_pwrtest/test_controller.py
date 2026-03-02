"""
Unit tests for PwrTestController.
All external I/O (subprocess, filesystem) is mocked.
"""

import threading
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from lib.testtool.pwrtest.controller import PwrTestController
from lib.testtool.pwrtest.exceptions import (
    PwrTestConfigError,
    PwrTestTimeoutError,
    PwrTestProcessError,
    PwrTestTestFailedError,
)


# Minimal valid kwargs that pass validate_config without touching the real FS
_VALID_KWARGS = {
    'executable_path': './bin/pwrtest.exe',
    'cycle_count':        1,
    'delay_seconds':      5,
    'wake_after_seconds': 30,
    'timeout_seconds':    120,
}


@pytest.fixture(autouse=True)
def patch_path_exists():
    """Prevent any Path.exists() call from touching the real filesystem."""
    with patch('pathlib.Path.exists', return_value=True):
        yield


@pytest.fixture
def ctrl():
    """Return a freshly constructed PwrTestController with minimal valid config."""
    return PwrTestController(**_VALID_KWARGS)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestPwrTestControllerInit:

    def test_is_thread(self, ctrl):
        assert isinstance(ctrl, threading.Thread)

    def test_status_initially_none(self, ctrl):
        assert ctrl.status is None

    def test_error_count_initially_zero(self, ctrl):
        assert ctrl.error_count == 0

    def test_result_summary_initially_empty(self, ctrl):
        assert ctrl.result_summary == {}

    def test_config_applied_from_kwargs(self, ctrl):
        assert ctrl._config['cycle_count'] == 1
        assert ctrl._config['timeout_seconds'] == 120

    def test_init_invalid_key_raises(self):
        with pytest.raises(PwrTestConfigError):
            PwrTestController(unknown_param='bad')

    def test_daemon_thread(self, ctrl):
        assert ctrl.daemon is True


# ---------------------------------------------------------------------------
# set_config
# ---------------------------------------------------------------------------

class TestPwrTestControllerSetConfig:

    def test_set_config_updates_value(self, ctrl):
        ctrl.set_config(cycle_count=5)
        assert ctrl._config['cycle_count'] == 5

    def test_set_config_invalid_key_raises(self, ctrl):
        with pytest.raises(PwrTestConfigError):
            ctrl.set_config(bad_key='value')

    def test_set_config_chained(self, ctrl):
        ctrl.set_config(cycle_count=2)
        ctrl.set_config(delay_seconds=15)
        assert ctrl._config['cycle_count'] == 2
        assert ctrl._config['delay_seconds'] == 15


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

class TestPwrTestControllerStop:

    def test_stop_sets_event(self, ctrl):
        assert not ctrl._stop_event.is_set()
        ctrl.stop()
        assert ctrl._stop_event.is_set()

    def test_stop_terminates_process_if_running(self, ctrl):
        mock_proc = Mock()
        mock_proc.poll.return_value = None
        ctrl._process = mock_proc
        ctrl.stop()
        mock_proc.terminate.assert_called_once()


# ---------------------------------------------------------------------------
# _build_command
# ---------------------------------------------------------------------------

class TestPwrTestControllerBuildCommand:

    def test_contains_sleep(self, ctrl):
        cmd = ctrl._build_command(Path('./bin/pwrtest.exe'))
        assert '/sleep' in cmd

    def test_cycle_count_arg(self, ctrl):
        ctrl.set_config(cycle_count=3)
        cmd = ctrl._build_command(Path('./bin/pwrtest.exe'))
        assert '/c:3' in cmd

    def test_delay_arg(self, ctrl):
        ctrl.set_config(delay_seconds=15)
        cmd = ctrl._build_command(Path('./bin/pwrtest.exe'))
        assert '/d:15' in cmd

    def test_wake_after_arg(self, ctrl):
        ctrl.set_config(wake_after_seconds=60)
        cmd = ctrl._build_command(Path('./bin/pwrtest.exe'))
        assert '/p:60' in cmd

    def test_no_log_prefix_by_default(self, ctrl):
        cmd = ctrl._build_command(Path('./bin/pwrtest.exe'))
        assert not any(a.startswith('/l:') for a in cmd)

    def test_log_prefix_included_when_set(self, ctrl):
        ctrl.set_config(log_prefix='mytest')
        cmd = ctrl._build_command(Path('./bin/pwrtest.exe'))
        assert '/l:mytest' in cmd


# ---------------------------------------------------------------------------
# run (mocked _execute_test)
# ---------------------------------------------------------------------------

class TestPwrTestControllerRun:

    def test_run_sets_true_when_execute_sets_status(self):
        with patch('pathlib.Path.exists', return_value=True):
            with patch.object(PwrTestController, '_execute_test') as mock_execute:
                c = PwrTestController(**_VALID_KWARGS)

                def fake_execute(self_inner=None):
                    c._status = True

                mock_execute.side_effect = fake_execute
                c.start()
                c.join(timeout=5)
                assert c.status is True

    @pytest.mark.parametrize("exc_class", [
        PwrTestTimeoutError,
        PwrTestProcessError,
        PwrTestTestFailedError,
        RuntimeError,
    ])
    def test_run_sets_false_on_exception(self, exc_class):
        with patch('pathlib.Path.exists', return_value=True):
            with patch.object(PwrTestController, '_execute_test',
                               side_effect=exc_class("error")):
                c = PwrTestController(**_VALID_KWARGS)
                c.start()
                c.join(timeout=5)
                assert c.status is False
