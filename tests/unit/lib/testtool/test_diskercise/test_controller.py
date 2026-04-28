"""
Unit tests for DiskerciseController.
All pywinauto and file-system interactions are mocked.
"""

import threading
import pytest
from unittest.mock import MagicMock, patch, call

from lib.testtool.diskercise.controller import DiskerciseController
from lib.testtool.diskercise.exceptions import (
    DiskerciseConfigError,
    DiskerciseTimeoutError,
    DiskerciseProcessError,
    DiskerciseTestFailedError,
)

# ---------------------------------------------------------------------------
# Shared valid kwargs
# ---------------------------------------------------------------------------

_VALID_KWARGS = {
    'exe_path': 'C:\\tools\\Diskercise\\Diskercise.exe',
    'test_duration_minutes': 1,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_path_exists():
    """Prevent __init__ from checking real file paths."""
    with patch('pathlib.Path.exists', return_value=True):
        yield


@pytest.fixture(autouse=True)
def patch_ui_monitor():
    """Replace DiskerciseUIMonitor with a mock so no pywinauto calls occur."""
    with patch('lib.testtool.diskercise.controller.DiskerciseUIMonitor') as MockMonitor:
        mock_monitor = MagicMock()
        mock_monitor.has_any_failure_popup.return_value = (False, '')
        MockMonitor.return_value = mock_monitor
        yield mock_monitor


@pytest.fixture
def ctrl(patch_ui_monitor):
    """Return a fresh, not-started controller."""
    return DiskerciseController(**_VALID_KWARGS)


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------

class TestDiskerciseControllerInit:

    def test_status_is_none(self, ctrl):
        assert ctrl.status is None

    def test_error_count_is_zero(self, ctrl):
        assert ctrl.error_count == 0

    def test_is_thread(self, ctrl):
        assert isinstance(ctrl, threading.Thread)

    def test_is_daemon(self, ctrl):
        assert ctrl.daemon is True

    def test_invalid_config_raises(self):
        with pytest.raises(DiskerciseConfigError):
            DiskerciseController(unknown_param='bad')

    def test_exe_path_from_env(self):
        with patch.dict('os.environ', {'DISKERCISE_PATH': 'C:\\tools\\Diskercise'}):
            ctrl = DiskerciseController()
        assert 'Diskercise.exe' in ctrl._config['exe_path']


# ---------------------------------------------------------------------------
# Tests: set_config
# ---------------------------------------------------------------------------

class TestDiskerciseControllerSetConfig:

    def test_updates_value(self, ctrl):
        ctrl.set_config(test_duration_minutes=60)
        assert ctrl._config['test_duration_minutes'] == 60

    def test_invalid_key_raises(self, ctrl):
        with pytest.raises(DiskerciseConfigError):
            ctrl.set_config(bad_key='value')


# ---------------------------------------------------------------------------
# Tests: stop
# ---------------------------------------------------------------------------

class TestDiskerciseControllerStop:

    def test_sets_stop_event(self, ctrl):
        assert not ctrl._stop_event.is_set()
        ctrl.stop()
        assert ctrl._stop_event.is_set()


# ---------------------------------------------------------------------------
# Tests: run() — mocked _execute_test
# ---------------------------------------------------------------------------

class TestDiskerciseControllerRun:

    def test_run_sets_true_on_success(self, ctrl):
        def fake_execute():
            ctrl._status = True

        with patch.object(DiskerciseController, '_execute_test', side_effect=fake_execute):
            ctrl.start()
            ctrl.join(timeout=5)

        assert ctrl.status is True

    @pytest.mark.parametrize("exc_cls", [
        DiskerciseTimeoutError,
        DiskerciseProcessError,
        DiskerciseTestFailedError,
    ])
    def test_run_sets_false_on_tool_exception(self, exc_cls):
        with patch.object(DiskerciseController, '_execute_test',
                          side_effect=exc_cls("err")):
            c = DiskerciseController(**_VALID_KWARGS)
            c.start()
            c.join(timeout=5)

        assert c.status is False

    def test_run_sets_false_on_unexpected_exception(self):
        with patch.object(DiskerciseController, '_execute_test',
                          side_effect=RuntimeError("unexpected")):
            c = DiskerciseController(**_VALID_KWARGS)
            c.start()
            c.join(timeout=5)

        assert c.status is False


# ---------------------------------------------------------------------------
# Tests: _scan_instances — failure popup
# ---------------------------------------------------------------------------

class TestDiskerciseScanInstances:

    def test_scan_detects_failure_popup(self, ctrl, patch_ui_monitor):
        """If a failure popup appears, status should be False."""
        patch_ui_monitor.has_any_failure_popup.return_value = (True, "Operation Failure - C")
        patch_ui_monitor.window_exists.return_value = True

        # pre-register a fake instance so controller enters multi-instance path
        fake_inst = MagicMock()
        ctrl._instances.append(fake_inst)

        ctrl.start()
        ctrl.join(timeout=5)

        assert ctrl.status is False
        assert "Operation Failure" in ctrl.failure_message

    def test_scan_stops_on_stop_event(self, ctrl, patch_ui_monitor):
        """stop() causes scan to exit cleanly (status True if no errors)."""
        patch_ui_monitor.has_any_failure_popup.return_value = (False, '')
        patch_ui_monitor.window_exists.return_value = True

        fake_inst = MagicMock()
        ctrl._instances.append(fake_inst)

        def _set_stop_on_sleep(_):
            ctrl._stop_event.set()

        with patch('lib.testtool.diskercise.controller.time.sleep',
                   side_effect=_set_stop_on_sleep):
            ctrl.start()
            ctrl.join(timeout=5)

        assert ctrl.status is True

    def test_scan_exits_after_duration(self, ctrl, patch_ui_monitor):
        """When duration elapses, controller clicks Stop and sets status True."""
        patch_ui_monitor.has_any_failure_popup.return_value = (False, '')
        patch_ui_monitor.window_exists.return_value = True

        fake_inst = MagicMock()
        ctrl._instances.append(fake_inst)

        # Make time.monotonic advance beyond duration on second call
        import time
        real_monotonic = time.monotonic
        calls = [0]

        def fast_monotonic():
            val = real_monotonic()
            if calls[0] == 0:
                calls[0] += 1
                return val
            # Return a value well past the 1-minute test duration (60s)
            return val + 120

        with patch('lib.testtool.diskercise.controller.time.monotonic',
                   side_effect=fast_monotonic), \
             patch('lib.testtool.diskercise.controller.time.sleep'):
            ctrl.start()
            ctrl.join(timeout=5)

        assert ctrl.status is True


# ---------------------------------------------------------------------------
# Tests: open_instance
# ---------------------------------------------------------------------------

class TestDiskerciseOpenInstance:

    def test_open_instance_registers_instance(self, ctrl, patch_ui_monitor):
        fake_inst = MagicMock()
        patch_ui_monitor.launch.return_value = fake_inst

        with patch('lib.testtool.diskercise.ui_monitor.DiskerciseUIMonitor.copy_exe_to_folder',
                   return_value='C:\\1\\Diskercise.exe'):
            idx = ctrl.open_instance('C:\\1')

        assert idx == 0
        assert len(ctrl._instances) == 1

    def test_open_instance_raises_on_copy_failure(self, ctrl):
        with patch('lib.testtool.diskercise.controller.DiskerciseUIMonitor.copy_exe_to_folder',
                   side_effect=OSError("disk full")):
            with pytest.raises(DiskerciseProcessError):
                ctrl.open_instance('C:\\1')


# ---------------------------------------------------------------------------
# Tests: start_all_instances
# ---------------------------------------------------------------------------

class TestDiskerciseStartAllInstances:

    def test_start_all_calls_click_start_for_each(self, ctrl, patch_ui_monitor):
        instances = [MagicMock(), MagicMock()]
        ctrl._instances.extend(instances)

        ctrl.start_all_instances()

        assert patch_ui_monitor.click_start.call_count == 2
