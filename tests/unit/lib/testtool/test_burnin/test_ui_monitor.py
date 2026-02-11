"""
Unit tests for BurnIN UI monitor module.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock, PropertyMock, call
from pathlib import Path

from lib.testtool.burnin.ui_monitor import BurnInUIMonitor
from lib.testtool.burnin.exceptions import (
    BurnInUIError,
    BurnInTimeoutError,
)


class TestBurnInUIMonitor:
    """Test suite for BurnInUIMonitor class."""
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_init(self, mock_app_class):
        """Test UI monitor initialization."""
        monitor = BurnInUIMonitor(
            window_title="PassMark BurnInTest",
            retry_max=30,
            retry_interval=2.0
        )
        
        assert monitor.window_title == "PassMark BurnInTest"
        assert monitor.retry_max == 30
        assert monitor.retry_interval == 2.0
        assert monitor._app is None
        assert monitor._window is None
        assert monitor._connected is False
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_init_default_values(self, mock_app_class):
        """Test initialization with default values."""
        monitor = BurnInUIMonitor()
        
        assert monitor.window_title == "PassMark BurnInTest"
        assert monitor.retry_max == 60
        assert monitor.retry_interval == 1.0
    
    @patch('lib.testtool.burnin.ui_monitor.Application', None)
    def test_init_no_pywinauto(self):
        """Test initialization fails without pywinauto."""
        with pytest.raises(ImportError) as exc_info:
            BurnInUIMonitor()
        
        assert 'pywinauto is required' in str(exc_info.value)
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    @patch('time.sleep')
    def test_connect_success(self, mock_sleep, mock_app_class):
        """Test successful window connection."""
        # Setup mocks
        mock_app = Mock()
        mock_window = Mock()
        mock_window.exists.return_value = True
        mock_app.window.return_value = mock_window
        
        mock_app_instance = Mock()
        mock_app_instance.connect.return_value = mock_app_instance
        mock_app_instance.window.return_value = mock_window
        mock_app_class.return_value = mock_app_instance
        
        # Execute
        monitor = BurnInUIMonitor()
        result = monitor.connect()
        
        # Verify
        assert result is True
        assert monitor._connected is True
        assert monitor._window is not None
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    @patch('lib.testtool.burnin.ui_monitor.ElementNotFoundError', Exception)
    @patch('time.sleep')
    def test_connect_retry_then_success(self, mock_sleep, mock_app_class):
        """Test connection succeeds after retries."""
        # Setup mocks - fail first time, succeed second time
        mock_app_instance = Mock()
        mock_window = Mock()
        
        call_count = [0]
        def connect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                from lib.testtool.burnin.ui_monitor import ElementNotFoundError
                raise ElementNotFoundError("Not found")
            return mock_app_instance
        
        mock_app_instance.connect = Mock(side_effect=connect_side_effect)
        mock_window.exists.return_value = True
        mock_app_instance.window.return_value = mock_window
        mock_app_class.return_value = mock_app_instance
        
        # Execute
        monitor = BurnInUIMonitor(retry_max=5)
        result = monitor.connect()
        
        # Verify
        assert result is True
        assert mock_sleep.called
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    @patch('lib.testtool.burnin.ui_monitor.ElementNotFoundError', Exception)
    @patch('time.sleep')
    def test_connect_timeout(self, mock_sleep, mock_app_class):
        """Test connection timeout after max retries."""
        # Setup mocks - always fail
        mock_app_instance = Mock()
        
        def connect_side_effect(*args, **kwargs):
            from lib.testtool.burnin.ui_monitor import ElementNotFoundError
            raise ElementNotFoundError("Not found")
        
        mock_app_instance.connect = Mock(side_effect=connect_side_effect)
        mock_app_class.return_value = mock_app_instance
        
        # Execute
        monitor = BurnInUIMonitor(retry_max=3)
        
        with pytest.raises(BurnInTimeoutError) as exc_info:
            monitor.connect()
        
        assert 'Failed to connect' in str(exc_info.value)
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_is_connected_true(self, mock_app_class):
        """Test is_connected returns True when connected."""
        monitor = BurnInUIMonitor()
        
        # Manually set connection state
        mock_window = Mock()
        mock_window.exists.return_value = True
        monitor._window = mock_window
        monitor._connected = True
        
        assert monitor.is_connected() is True
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_is_connected_false_not_connected(self, mock_app_class):
        """Test is_connected returns False when not connected."""
        monitor = BurnInUIMonitor()
        
        assert monitor.is_connected() is False
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_is_connected_false_window_gone(self, mock_app_class):
        """Test is_connected returns False when window no longer exists."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = False
        monitor._window = mock_window
        monitor._connected = True
        
        assert monitor.is_connected() is False
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_disconnect(self, mock_app_class):
        """Test disconnect."""
        monitor = BurnInUIMonitor()
        monitor._window = Mock()
        monitor._app = Mock()
        monitor._connected = True
        
        monitor.disconnect()
        
        assert monitor._window is None
        assert monitor._app is None
        assert monitor._connected is False
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_read_status_not_connected(self, mock_app_class):
        """Test read_status fails when not connected."""
        monitor = BurnInUIMonitor()
        
        with pytest.raises(BurnInUIError) as exc_info:
            monitor.read_status()
        
        assert 'Not connected' in str(exc_info.value)
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_read_status_running(self, mock_app_class):
        """Test read_status when test is running."""
        monitor = BurnInUIMonitor()
        
        # Setup mock window
        mock_window = Mock()
        mock_window.exists.return_value = True
        mock_window.window_text.return_value = "BurnInTest - Running - 0 errors"
        monitor._window = mock_window
        monitor._connected = True
        
        status = monitor.read_status()
        
        assert status['test_running'] is True
        assert status['test_result'] == 'running'
        assert status['errors'] == 0
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_read_status_passed(self, mock_app_class):
        """Test read_status when test passed."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        mock_window.window_text.return_value = "BurnInTest - TEST PASSED - 0 errors"
        monitor._window = mock_window
        monitor._connected = True
        
        status = monitor.read_status()
        
        assert status['test_result'] == 'passed'
        assert status['errors'] == 0
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_read_status_failed(self, mock_app_class):
        """Test read_status when test failed."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        mock_window.window_text.return_value = "BurnInTest - TEST FAILED - 5 errors"
        monitor._window = mock_window
        monitor._connected = True
        
        status = monitor.read_status()
        
        assert status['test_result'] == 'failed'
        assert status['errors'] == 5
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_get_error_count(self, mock_app_class):
        """Test get_error_count."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        mock_window.window_text.return_value = "BurnInTest - Running - 3 errors"
        monitor._window = mock_window
        monitor._connected = True
        
        errors = monitor.get_error_count()
        
        assert errors == 3
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_is_test_running(self, mock_app_class):
        """Test is_test_running."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        mock_window.window_text.return_value = "BurnInTest - Running"
        monitor._window = mock_window
        monitor._connected = True
        
        assert monitor.is_test_running() is True
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    @patch('time.sleep')
    def test_wait_for_completion_passed(self, mock_sleep, mock_app_class):
        """Test wait_for_completion when test passes."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        
        # First call: running, second call: passed
        call_count = [0]
        def window_text_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return "BurnInTest - Running"
            else:
                return "BurnInTest - TEST PASSED"
        
        mock_window.window_text = Mock(side_effect=window_text_side_effect)
        monitor._window = mock_window
        monitor._connected = True
        
        result = monitor.wait_for_completion(timeout=10, check_interval=1)
        
        assert result == 'passed'
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    @patch('time.sleep')
    def test_wait_for_completion_timeout(self, mock_sleep, mock_app_class):
        """Test wait_for_completion timeout."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        mock_window.window_text.return_value = "BurnInTest - Running"
        monitor._window = mock_window
        monitor._connected = True
        
        # Make time.sleep actually pass time for timeout
        original_time = time.time
        elapsed = [0]
        
        def fake_sleep(seconds):
            elapsed[0] += seconds
        
        def fake_time():
            return original_time() + elapsed[0]
        
        mock_sleep.side_effect = fake_sleep
        
        with patch('time.time', fake_time):
            result = monitor.wait_for_completion(timeout=5, check_interval=1)
        
        assert result == 'timeout'
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_handle_dialogs_no_dialogs(self, mock_app_class):
        """Test handle_dialogs when no dialogs present."""
        monitor = BurnInUIMonitor()
        
        mock_app = Mock()
        mock_window = Mock()
        mock_window.exists.return_value = True
        
        # No dialogs found
        mock_dialog = Mock()
        mock_dialog.exists.return_value = False
        mock_app.window.return_value = mock_dialog
        
        monitor._app = mock_app
        monitor._window = mock_window
        monitor._connected = True
        
        result = monitor.handle_dialogs()
        
        assert result is False
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_handle_dialogs_with_ok_button(self, mock_app_class):
        """Test handle_dialogs clicks OK button."""
        monitor = BurnInUIMonitor()
        
        mock_app = Mock()
        mock_window = Mock()
        mock_window.exists.return_value = True
        
        # Dialog with OK button
        mock_dialog = Mock()
        mock_dialog.exists.return_value = True
        mock_ok = Mock()
        mock_ok.exists.return_value = True
        mock_dialog.OK = mock_ok
        mock_app.window.return_value = mock_dialog
        
        monitor._app = mock_app
        monitor._window = mock_window
        monitor._connected = True
        
        result = monitor.handle_dialogs()
        
        assert result is True
        mock_ok.click.assert_called_once()
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    @patch('os.makedirs')
    def test_take_screenshot_success(self, mock_makedirs, mock_app_class):
        """Test take_screenshot."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        
        mock_image = Mock()
        mock_window.capture_as_image.return_value = mock_image
        
        monitor._window = mock_window
        monitor._connected = True
        
        path = monitor.take_screenshot("./test.png")
        
        assert path == "./test.png"
        mock_image.save.assert_called_once_with("./test.png")
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_take_screenshot_not_connected(self, mock_app_class):
        """Test take_screenshot fails when not connected."""
        monitor = BurnInUIMonitor()
        
        with pytest.raises(BurnInUIError) as exc_info:
            monitor.take_screenshot("./test.png")
        
        assert 'Not connected' in str(exc_info.value)
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_click_button_success(self, mock_app_class):
        """Test click_button."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        
        mock_button = Mock()
        mock_button.exists.return_value = True
        mock_window.child_window.return_value = mock_button
        
        monitor._window = mock_window
        monitor._connected = True
        
        result = monitor.click_button("Start")
        
        assert result is True
        mock_button.click.assert_called_once()
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_click_button_not_found(self, mock_app_class):
        """Test click_button when button not found."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        
        mock_button = Mock()
        mock_button.exists.return_value = False
        mock_window.child_window.return_value = mock_button
        
        monitor._window = mock_window
        monitor._connected = True
        
        with pytest.raises(BurnInUIError) as exc_info:
            monitor.click_button("Start")
        
        assert 'not found' in str(exc_info.value)
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_get_window_info(self, mock_app_class):
        """Test get_window_info."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        mock_window.window_text.return_value = "BurnInTest"
        mock_window.is_visible.return_value = True
        mock_window.is_enabled.return_value = True
        mock_window.rectangle.return_value = (100, 100, 800, 600)
        
        monitor._window = mock_window
        monitor._connected = True
        
        info = monitor.get_window_info()
        
        assert info['title'] == "BurnInTest"
        assert info['visible'] is True
        assert info['enabled'] is True
        assert info['rect'] == (100, 100, 800, 600)
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    @patch('time.sleep')
    def test_wait_for_window_success(self, mock_sleep, mock_app_class):
        """Test wait_for_window when window appears."""
        monitor = BurnInUIMonitor()
        
        # Mock successful connection on first try
        with patch.object(monitor, 'connect', return_value=True):
            result = monitor.wait_for_window(timeout=10)
        
        assert result is True
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    @patch('time.sleep')
    def test_wait_for_window_timeout(self, mock_sleep, mock_app_class):
        """Test wait_for_window timeout."""
        monitor = BurnInUIMonitor()
        
        # Mock failed connection
        with patch.object(monitor, 'connect', side_effect=BurnInUIError("Not found")):
            # Mock time for timeout
            original_time = time.time
            elapsed = [0]
            
            def fake_sleep(seconds):
                elapsed[0] += seconds
            
            def fake_time():
                return original_time() + elapsed[0]
            
            mock_sleep.side_effect = fake_sleep
            
            with patch('time.time', fake_time):
                with pytest.raises(BurnInTimeoutError) as exc_info:
                    monitor.wait_for_window(timeout=5)
            
            assert 'did not appear' in str(exc_info.value)
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_read_text_field_success(self, mock_app_class):
        """Test read_text_field."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        
        mock_field = Mock()
        mock_field.exists.return_value = True
        mock_field.window_text.return_value = "12:34:56"
        mock_window.child_window.return_value = mock_field
        
        monitor._window = mock_window
        monitor._connected = True
        
        text = monitor.read_text_field("ElapsedTime")
        
        assert text == "12:34:56"
    
    @patch('lib.testtool.burnin.ui_monitor.Application')
    def test_read_text_field_not_found(self, mock_app_class):
        """Test read_text_field when field not found."""
        monitor = BurnInUIMonitor()
        
        mock_window = Mock()
        mock_window.exists.return_value = True
        
        mock_field = Mock()
        mock_field.exists.return_value = False
        mock_window.child_window.return_value = mock_field
        
        monitor._window = mock_window
        monitor._connected = True
        
        with pytest.raises(BurnInUIError) as exc_info:
            monitor.read_text_field("NonExistent")
        
        assert 'not found' in str(exc_info.value)
