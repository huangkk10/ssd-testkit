"""
Unit tests for BurnIN Controller

Tests the BurnInController class with mocked dependencies.
"""

from unittest.mock import Mock, MagicMock, patch, call
import threading
import time
from pathlib import Path

from lib.testtool.burnin.controller import BurnInController
from lib.testtool.burnin.exceptions import (
    BurnInError,
    BurnInConfigError,
    BurnInTimeoutError,
    BurnInProcessError,
    BurnInInstallError,
    BurnInUIError,
    BurnInTestFailedError,
)
import pytest


class TestBurnInController:
    """Test cases for BurnInController"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.test_installer = "C:\\test\\installer.exe"
        self.test_install_path = "C:\\Program Files\\BurnInTest"
        self.test_executable = "bit.exe"
        
        # Create mock installer file
        self.mock_installer_exists = patch('pathlib.Path.exists', return_value=True)
        self.mock_installer_exists.start()
        
        # Mock logger
        self.mock_logger = patch('lib.testtool.burnin.controller.logConfig')
        self.mock_logger.start()
    
    def teardown_method(self):
        """Clean up after tests"""
        self.mock_installer_exists.stop()
        self.mock_logger.stop()
    
    # ===== Initialization Tests =====
    
    def test_init_basic(self):
        """Test basic initialization"""
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path,
            executable_name=self.test_executable
        )
        
        assert controller.installer_path == self.test_installer
        assert controller.install_path == self.test_install_path
        assert controller.executable_name == self.test_executable
        assert controller.status
        assert controller.error_count == 0
        assert not controller._running
    
    def test_init_with_custom_config(self):
        """Test initialization with custom configuration"""
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path,
            executable_name=self.test_executable,
            test_duration_minutes=120,
            test_drive_letter="E",
            timeout_seconds=7200
        )
        
        assert controller.test_duration_minutes == 120
        assert controller.test_drive_letter == "E"
        assert controller.timeout_seconds == 7200
    
    @patch('pathlib.Path.exists', return_value=False)
    def test_init_installer_not_found(self, mock_exists):
        """Test initialization with missing installer"""
        with pytest.raises(BurnInConfigError):
            BurnInController(
                installer_path="nonexistent.exe",
                install_path=self.test_install_path
            )
        
        assert "Installer not found" in str(ctx.exception)
    
    def test_init_default_values(self):
        """Test initialization with default values"""
        controller = BurnInController(
            installer_path=self.test_installer
        )
        
        assert controller.install_path == "C:\\Program Files\\BurnInTest"
        assert controller.executable_name == "bit.exe"
        assert controller.test_duration_minutes == 1440
        assert controller.test_drive_letter == "D"
    
    # ===== Installation Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_install_success(self, mock_manager_class):
        """Test successful installation"""
        mock_manager = Mock()
        mock_manager.install.return_value = True
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        result = controller.install()
        
        assert result
        mock_manager.install.assert_called_once()
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_install_with_license(self, mock_manager_class):
        """Test installation with license file"""
        mock_manager = Mock()
        mock_manager.install.return_value = True
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        result = controller.install(license_path="C:\\test\\license.key")
        
        assert result
        call_args = mock_manager.install.call_args
        assert call_args[1]['license_path'] == "C:\\test\\license.key"
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_install_failure(self, mock_manager_class):
        """Test installation failure"""
        mock_manager = Mock()
        mock_manager.install.return_value = False
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        with pytest.raises(BurnInInstallError):
            controller.install()
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_install_exception(self, mock_manager_class):
        """Test installation with exception"""
        mock_manager = Mock()
        mock_manager.install.side_effect = Exception("Install error")
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        with pytest.raises(BurnInInstallError):
            controller.install()
        
        assert "Install error" in str(ctx.exception)
    
    # ===== Uninstallation Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_uninstall_success(self, mock_manager_class):
        """Test successful uninstallation"""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.uninstall.return_value = True
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        
        result = controller.uninstall()
        
        assert result
        mock_manager.uninstall.assert_called_once()
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_uninstall_with_running_process(self, mock_manager_class):
        """Test uninstallation stops running process first"""
        mock_manager = Mock()
        mock_manager.is_running.return_value = True
        mock_manager.stop_process.return_value = True
        mock_manager.uninstall.return_value = True
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        
        result = controller.uninstall()
        
        assert result
        mock_manager.stop_process.assert_called_once()
        mock_manager.uninstall.assert_called_once()
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_uninstall_failure(self, mock_manager_class):
        """Test uninstallation failure"""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.uninstall.side_effect = Exception("Uninstall error")
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        
        with pytest.raises(BurnInInstallError):
            controller.uninstall()
    
    # ===== Installation Check Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_is_installed_true(self, mock_manager_class):
        """Test is_installed when software is installed"""
        mock_manager = Mock()
        mock_manager.is_installed.return_value = True
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        result = controller.is_installed()
        
        assert result
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_is_installed_false(self, mock_manager_class):
        """Test is_installed when software is not installed"""
        mock_manager = Mock()
        mock_manager.is_installed.return_value = False
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        result = controller.is_installed()
        
        assert not result
    
    # ===== Configuration Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInConfig')
    def test_set_config_valid(self, mock_config):
        """Test setting valid configuration"""
        mock_config.validate_config.return_value = True
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        controller.set_config(
            test_duration_minutes=120,
            test_drive_letter="E",
            timeout_seconds=7200
        )
        
        assert controller.test_duration_minutes == 120
        assert controller.test_drive_letter == "E"
        assert controller.timeout_seconds == 7200
    
    @patch('lib.testtool.burnin.controller.BurnInConfig')
    def test_set_config_invalid(self, mock_config):
        """Test setting invalid configuration"""
        mock_config.validate_config.side_effect = ValueError("Invalid config")
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        with pytest.raises(BurnInConfigError):
            controller.set_config(invalid_param="value")
    
    # ===== Script Generation Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInScriptGenerator')
    def test_generate_script_success(self, mock_generator_class):
        """Test successful script generation"""
        mock_generator = Mock()
        mock_generator_class.return_value = mock_generator
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._script_generator = mock_generator
        
        controller._generate_script()
        
        mock_generator.generate_disk_test_script.assert_called_once()
    
    @patch('lib.testtool.burnin.controller.BurnInScriptGenerator')
    def test_generate_script_failure(self, mock_generator_class):
        """Test script generation failure"""
        mock_generator = Mock()
        mock_generator.generate_disk_test_script.side_effect = Exception("Script error")
        mock_generator_class.return_value = mock_generator
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._script_generator = mock_generator
        
        with pytest.raises(BurnInConfigError):
            controller._generate_script()
    
    # ===== Process Start Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_start_process_success(self, mock_manager_class):
        """Test successful process start"""
        mock_manager = Mock()
        mock_manager.start_process.return_value = 1234
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        
        controller._start_process()
        
        mock_manager.start_process.assert_called_once()
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_start_process_failure(self, mock_manager_class):
        """Test process start failure"""
        mock_manager = Mock()
        mock_manager.start_process.return_value = None
        mock_manager_class.return_value = mock_manager
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        
        with pytest.raises(BurnInProcessError):
            controller._start_process()
    
    def test_start_process_no_manager(self):
        """Test process start without manager"""
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        with pytest.raises(BurnInProcessError):
            controller._start_process()
    
    # ===== UI Connection Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    def test_connect_ui_success(self, mock_monitor_class):
        """Test successful UI connection"""
        mock_monitor = Mock()
        mock_monitor.connect.return_value = True
        mock_monitor_class.return_value = mock_monitor
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        controller._connect_ui()
        
        mock_monitor.connect.assert_called_once()
    
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    def test_connect_ui_failure(self, mock_monitor_class):
        """Test UI connection failure"""
        mock_monitor = Mock()
        mock_monitor.connect.return_value = False
        mock_monitor_class.return_value = mock_monitor
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        with pytest.raises(BurnInUIError):
            controller._connect_ui()
    
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    def test_connect_ui_exception(self, mock_monitor_class):
        """Test UI connection exception"""
        mock_monitor = Mock()
        mock_monitor.connect.side_effect = Exception("Connection error")
        mock_monitor_class.return_value = mock_monitor
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        with pytest.raises(BurnInUIError):
            controller._connect_ui()
    
    # ===== Monitoring Loop Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    def test_monitor_loop_passed(self, mock_monitor_class):
        """Test monitoring loop with PASSED status"""
        mock_monitor = Mock()
        mock_monitor.read_status.return_value = "PASSED"
        mock_monitor.get_error_count.return_value = 0
        mock_monitor.take_screenshot.return_value = None
        mock_monitor.handle_dialogs.return_value = None
        mock_monitor_class.return_value = mock_monitor
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path,
            check_interval_seconds=0.1
        )
        controller._ui_monitor = mock_monitor
        
        controller._monitor_loop()
        
        assert controller.status
        assert controller._test_result == "PASSED"
        assert controller.error_count == 0
    
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    def test_monitor_loop_failed(self, mock_monitor_class):
        """Test monitoring loop with FAILED status"""
        mock_monitor = Mock()
        mock_monitor.read_status.return_value = "FAILED"
        mock_monitor.get_error_count.return_value = 5
        mock_monitor.take_screenshot.return_value = None
        mock_monitor.handle_dialogs.return_value = None
        mock_monitor_class.return_value = mock_monitor
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path,
            check_interval_seconds=0.1
        )
        controller._ui_monitor = mock_monitor
        
        with pytest.raises(BurnInTestFailedError):
            controller._monitor_loop()
        
        assert not controller.status
        assert controller._test_result == "FAILED"
        assert controller.error_count == 5
    
    @patch('lib.testtool.burnin.controller.time')
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    def test_monitor_loop_timeout(self, mock_monitor_class, mock_time_module):
        """Test monitoring loop timeout"""
        # Simulate time passing - use infinite generator for time()
        time_values = iter([0, 0, 10000, 10001, 10002])  # Start, check, timeout, ...
        mock_time_module.time.side_effect = lambda: next(time_values)
        mock_time_module.strftime.return_value = "20260211_111710"
        mock_time_module.sleep.return_value = None
        
        mock_monitor = Mock()
        mock_monitor.read_status.return_value = "RUNNING"
        mock_monitor.take_screenshot.return_value = None
        mock_monitor.handle_dialogs.return_value = None
        mock_monitor_class.return_value = mock_monitor
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path,
            timeout_seconds=100,
            check_interval_seconds=0.1
        )
        controller._ui_monitor = mock_monitor
        
        with pytest.raises(BurnInTimeoutError):
            controller._monitor_loop()
        
        assert not controller.status
    
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    def test_monitor_loop_ui_reconnect(self, mock_monitor_class):
        """Test monitoring loop UI reconnection"""
        mock_monitor = Mock()
        # First call raises error, then returns status
        mock_monitor.read_status.side_effect = [
            BurnInUIError("Connection lost"),
            "PASSED"
        ]
        mock_monitor.is_connected.return_value = False
        mock_monitor.connect.return_value = True
        mock_monitor.get_error_count.return_value = 0
        mock_monitor.take_screenshot.return_value = None
        mock_monitor.handle_dialogs.return_value = None
        mock_monitor_class.return_value = mock_monitor
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path,
            check_interval_seconds=0.1
        )
        controller._ui_monitor = mock_monitor
        
        controller._monitor_loop()
        
        # Should have reconnected
        mock_monitor.connect.assert_called()
        assert controller.status
    
    # ===== Stop Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    def test_stop_running_process(self, mock_monitor_class, mock_manager_class):
        """Test stopping running process"""
        mock_manager = Mock()
        mock_manager.stop_process.return_value = True
        mock_monitor = Mock()
        mock_monitor.is_connected.return_value = True
        mock_monitor.disconnect.return_value = None
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        controller._ui_monitor = mock_monitor
        
        controller.stop()
        
        mock_monitor.disconnect.assert_called_once()
        mock_manager.stop_process.assert_called_once()
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_stop_with_kill(self, mock_manager_class):
        """Test stop that requires kill"""
        mock_manager = Mock()
        mock_manager.stop_process.side_effect = Exception("Stop failed")
        mock_manager.kill_process.return_value = True
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        
        controller.stop()
        
        mock_manager.kill_process.assert_called_once()
    
    # ===== Running Status Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_is_running_true(self, mock_manager_class):
        """Test is_running when process is running"""
        mock_manager = Mock()
        mock_manager.is_running.return_value = True
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        
        result = controller.is_running()
        
        assert result
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_is_running_false(self, mock_manager_class):
        """Test is_running when process is not running"""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        
        result = controller.is_running()
        
        assert not result
    
    def test_is_running_no_manager(self):
        """Test is_running without manager"""
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        result = controller.is_running()
        
        assert not result
    
    # ===== Status Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_get_status(self, mock_manager_class):
        """Test get_status method"""
        mock_manager = Mock()
        mock_manager.is_installed.return_value = True
        mock_manager.is_running.return_value = True
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        controller._running = True
        controller.status = True
        controller._test_result = "PASSED"
        controller.error_count = 0
        
        status = controller.get_status()
        
        assert status['running']
        assert status['status']
        assert status['test_result'] == "PASSED"
        assert status['error_count'] == 0
        assert status['installed']
        assert status['process_running']
    
    # ===== Screenshot Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    @patch('pathlib.Path.mkdir')
    def test_take_screenshot_success(self, mock_mkdir, mock_monitor_class):
        """Test successful screenshot"""
        mock_monitor = Mock()
        mock_monitor.take_screenshot.return_value = None
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path,
            enable_screenshot=True
        )
        controller._ui_monitor = mock_monitor
        
        controller._take_screenshot("test")
        
        mock_monitor.take_screenshot.assert_called_once()
    
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    def test_take_screenshot_disabled(self, mock_monitor_class):
        """Test screenshot when disabled"""
        mock_monitor = Mock()
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path,
            enable_screenshot=False
        )
        controller._ui_monitor = mock_monitor
        
        controller._take_screenshot("test")
        
        mock_monitor.take_screenshot.assert_not_called()
    
    # ===== Thread Run Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInUIMonitor')
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    @patch('lib.testtool.burnin.controller.BurnInScriptGenerator')
    @patch('time.sleep')
    def test_run_success(self, mock_sleep, mock_generator_class, 
                         mock_manager_class, mock_monitor_class):
        """Test successful run execution"""
        # Setup mocks
        mock_generator = Mock()
        mock_generator.generate_disk_test_script.return_value = None
        mock_generator_class.return_value = mock_generator
        
        mock_manager = Mock()
        mock_manager.start_process.return_value = 1234
        mock_manager_class.return_value = mock_manager
        
        mock_monitor = Mock()
        mock_monitor.connect.return_value = True
        mock_monitor.read_status.return_value = "PASSED"
        mock_monitor.get_error_count.return_value = 0
        mock_monitor.take_screenshot.return_value = None
        mock_monitor.handle_dialogs.return_value = None
        mock_monitor_class.return_value = mock_monitor
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path,
            check_interval_seconds=0.1
        )
        # Initialize process manager for the controller
        controller._process_manager = mock_manager
        
        controller.run()
        
        assert controller.status
        assert not controller._running
    
    @patch('lib.testtool.burnin.controller.BurnInScriptGenerator')
    def test_run_script_generation_failure(self, mock_generator_class):
        """Test run with script generation failure"""
        mock_generator = Mock()
        mock_generator.generate_disk_test_script.side_effect = Exception("Script error")
        mock_generator_class.return_value = mock_generator
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        
        controller.run()
        
        assert not controller.status
    
    # ===== Repr Tests =====
    
    @patch('lib.testtool.burnin.controller.BurnInProcessManager')
    def test_repr(self, mock_manager_class):
        """Test string representation"""
        mock_manager = Mock()
        mock_manager.is_installed.return_value = True
        
        controller = BurnInController(
            installer_path=self.test_installer,
            install_path=self.test_install_path
        )
        controller._process_manager = mock_manager
        
        repr_str = repr(controller)
        
        assert "BurnInController" in repr_str
        assert "installed=True" in repr_str
        assert "running=False" in repr_str
        assert "status=True" in repr_str


