"""
Unit tests for DiskerciseUIMonitor.
All pywinauto calls are mocked — no real Diskercise.exe is launched.
"""

import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from lib.testtool.diskercise.ui_monitor import DiskerciseUIMonitor, DiskerciseInstance
from lib.testtool.diskercise.exceptions import DiskerciseUIError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_instance(exe_path='C:\\tools\\Diskercise\\Diskercise.exe'):
    """Create a DiskerciseInstance with mocked app and window."""
    app = MagicMock()
    window = MagicMock()
    window.exists.return_value = True
    return DiskerciseInstance(app=app, window=window, exe_path=exe_path)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def monitor():
    """DiskerciseUIMonitor with pywinauto import mocked away."""
    with patch('lib.testtool.diskercise.ui_monitor.Application', MagicMock()):
        m = DiskerciseUIMonitor(window_wait_timeout=5, ui_retry_max=2)
    return m


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------

class TestDiskerciseUIMonitorInit:

    def test_attributes_set(self, monitor):
        assert monitor.window_wait_timeout == 5
        assert monitor.ui_retry_max == 2

    def test_raises_if_no_pywinauto(self):
        with patch('lib.testtool.diskercise.ui_monitor.Application', None):
            with pytest.raises(ImportError):
                DiskerciseUIMonitor()


# ---------------------------------------------------------------------------
# Tests: launch
# ---------------------------------------------------------------------------

class TestDiskerciseUIMonitorLaunch:

    def test_launch_returns_instance(self):
        mock_app = MagicMock()
        mock_window = MagicMock()
        mock_window.exists.return_value = True
        mock_app.window.return_value = mock_window

        with patch('lib.testtool.diskercise.ui_monitor.Application') as MockApp:
            MockApp.return_value.start.return_value = mock_app
            mock_app.window.return_value = mock_window

            monitor = DiskerciseUIMonitor()
            inst = monitor.launch('C:\\tools\\Diskercise.exe')

        assert isinstance(inst, DiskerciseInstance)

    def test_launch_kills_app_on_window_error(self):
        mock_app = MagicMock()
        mock_window = MagicMock()
        mock_window.wait.side_effect = Exception("window not found")
        mock_app.window.return_value = mock_window

        with patch('lib.testtool.diskercise.ui_monitor.Application') as MockApp:
            MockApp.return_value.start.return_value = mock_app

            monitor = DiskerciseUIMonitor()
            with pytest.raises(DiskerciseUIError):
                monitor.launch('C:\\tools\\Diskercise.exe')

        mock_app.kill.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: close
# ---------------------------------------------------------------------------

class TestDiskerciseUIMonitorClose:

    def test_close_instance_kills_app(self, monitor):
        inst = _make_instance()
        monitor.close_instance(inst)
        inst.app.kill.assert_called_once()

    def test_close_all_kills_all(self, monitor):
        instances = [_make_instance() for _ in range(3)]
        monitor.close_all(instances)
        for inst in instances:
            inst.app.kill.assert_called_once()

    def test_close_instance_tolerates_kill_failure(self, monitor):
        inst = _make_instance()
        inst.app.kill.side_effect = Exception("already dead")
        monitor.close_instance(inst)  # should not raise


# ---------------------------------------------------------------------------
# Tests: failure popup detection
# ---------------------------------------------------------------------------

class TestDiskerciseUIMonitorFailureDetection:

    def test_no_failure_when_no_bad_windows(self, monitor):
        inst = _make_instance()
        mock_win = MagicMock()
        mock_win.element_info.name = "Diskercise"
        inst.app.windows.return_value = [mock_win]

        found, msg = monitor.has_failure_popup(inst)
        assert found is False
        assert msg == ''

    def test_detects_operation_failure_popup(self, monitor):
        inst = _make_instance()
        bad_win = MagicMock()
        bad_win.element_info.name = "Operation Failure - Drive C"
        inst.app.windows.return_value = [bad_win]

        found, msg = monitor.has_failure_popup(inst)
        assert found is True
        assert "Operation Failure" in msg

    def test_has_any_failure_popup_checks_all(self, monitor):
        inst1 = _make_instance()
        inst1.app.windows.return_value = []

        inst2 = _make_instance()
        bad_win = MagicMock()
        bad_win.element_info.name = "Operation Failure - Drive D"
        inst2.app.windows.return_value = [bad_win]

        found, msg = monitor.has_any_failure_popup([inst1, inst2])
        assert found is True

    def test_has_any_failure_popup_no_failures(self, monitor):
        instances = [_make_instance() for _ in range(2)]
        for inst in instances:
            inst.app.windows.return_value = []

        found, _ = monitor.has_any_failure_popup(instances)
        assert found is False


# ---------------------------------------------------------------------------
# Tests: window_exists
# ---------------------------------------------------------------------------

class TestDiskerciseUIMonitorWindowExists:

    def test_returns_true_when_window_exists(self, monitor):
        inst = _make_instance()
        inst.window.exists.return_value = True
        assert monitor.window_exists(inst) is True

    def test_returns_false_when_window_gone(self, monitor):
        inst = _make_instance()
        inst.window.exists.return_value = False
        assert monitor.window_exists(inst) is False

    def test_returns_false_on_exception(self, monitor):
        inst = _make_instance()
        inst.window.exists.side_effect = Exception("crash")
        assert monitor.window_exists(inst) is False


# ---------------------------------------------------------------------------
# Tests: copy_exe_to_folder
# ---------------------------------------------------------------------------

class TestDiskerciseCopyExe:

    def test_copy_exe_creates_file(self, tmp_path):
        src = tmp_path / "Diskercise.exe"
        src.write_bytes(b"fake exe content")
        dest_folder = str(tmp_path / "dest")

        result = DiskerciseUIMonitor.copy_exe_to_folder(str(src), dest_folder)

        assert os.path.isfile(result)
        assert os.path.basename(result) == "Diskercise.exe"

    def test_copy_exe_creates_dest_folder(self, tmp_path):
        src = tmp_path / "Diskercise.exe"
        src.write_bytes(b"fake exe")
        dest_folder = str(tmp_path / "new_folder" / "sub")

        DiskerciseUIMonitor.copy_exe_to_folder(str(src), dest_folder)

        assert os.path.isdir(dest_folder)
