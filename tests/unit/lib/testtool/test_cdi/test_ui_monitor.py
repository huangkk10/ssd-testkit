"""
Unit tests for CDI UI Monitor.
All pywinauto calls are mocked — no real UI interaction.
"""

from unittest.mock import MagicMock, Mock, patch

from lib.testtool.cdi.ui_monitor import CDIUIMonitor
from lib.testtool.cdi.exceptions import CDIUIError
import pytest


class TestCDIUIMonitor:

    def setup_method(self):
        self.monitor = CDIUIMonitor(save_retry_max=3, save_dialog_timeout=5)

    # ----- Construction -----

    def test_init_defaults(self):
        m = CDIUIMonitor()
        assert 'CrystalDiskInfo' in m.window_title
        assert m._app is None
        assert m._window is None

    def test_init_custom_params(self):
        m = CDIUIMonitor(window_title='MyTool', save_retry_max=5)
        assert m.window_title == 'MyTool'
        assert m.save_retry_max == 5

    # ----- open(): pywinauto unavailable -----

    def test_open_raises_when_pywinauto_unavailable(self):
        with patch('lib.testtool.cdi.ui_monitor._PYWINAUTO_AVAILABLE', False):
            m = CDIUIMonitor()
            with pytest.raises(CDIUIError):
                m.open('./bin/DiskInfo64.exe')

    # ----- open(): success path -----

    @patch('lib.testtool.cdi.ui_monitor.Application')
    @patch('lib.testtool.cdi.ui_monitor._PYWINAUTO_AVAILABLE', True)
    @patch('lib.testtool.cdi.ui_monitor.time.sleep')
    def test_open_success(self, mock_sleep, mock_app_class):
        mock_app = MagicMock()
        mock_window = MagicMock()
        mock_app_class.return_value.start.return_value = mock_app
        mock_app.window.return_value = mock_window

        m = CDIUIMonitor()
        m.open('./bin/DiskInfo64.exe')

        mock_app_class.return_value.start.assert_called_once()
        mock_window.wait.assert_called_once()

    # ----- connect(): pywinauto unavailable -----

    def test_connect_raises_when_pywinauto_unavailable(self):
        with patch('lib.testtool.cdi.ui_monitor._PYWINAUTO_AVAILABLE', False):
            m = CDIUIMonitor()
            with pytest.raises(CDIUIError):
                m.connect()

    # ----- close -----

    def test_close_kills_app(self):
        monitor = CDIUIMonitor()
        mock_app = MagicMock()
        monitor._app = mock_app
        monitor._window = MagicMock()

        with patch('lib.testtool.cdi.ui_monitor.time.sleep'):
            monitor.close()

        mock_app.kill.assert_called_once()
        assert monitor._app is None
        assert monitor._window is None

    def test_close_with_no_app_does_not_raise(self):
        monitor = CDIUIMonitor()
        monitor._app = None
        with patch('lib.testtool.cdi.ui_monitor.time.sleep'):
            monitor.close()  # must not raise

    # ----- get_text_log: raises when not connected -----

    def test_get_text_log_raises_when_not_connected(self):
        m = CDIUIMonitor()
        with pytest.raises(CDIUIError):
            m.get_text_log('/tmp/DiskInfo.txt')

    # ----- get_screenshot: raises when not connected -----

    def test_get_screenshot_raises_when_not_connected(self):
        m = CDIUIMonitor()
        with pytest.raises(CDIUIError):
            m.get_screenshot(
                log_dir='/tmp',
                prefix='',
                drive_letter='',
                diskinfo_json_path='/tmp/DiskInfo.json',
            )

    # ----- _get_drive_info_from_json -----

    def test_get_drive_info_from_json_success(self, *_):
        import json
        import tempfile
        import os

        data = {'disks': [{'Model': 'TestDrive', 'Drive Letter': 'C:', 'DiskNum': '1'}]}
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            result = CDIUIMonitor._get_drive_info_from_json(path, 'C:', 'Model')
            assert result == 'TestDrive'
        finally:
            os.unlink(path)

    def test_get_drive_info_from_json_missing_drive(self, *_):
        import json
        import tempfile
        import os

        data = {'disks': []}
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            with pytest.raises(CDIUIError):
                CDIUIMonitor._get_drive_info_from_json(path, 'Z:', 'Model')
        finally:
            os.unlink(path)


