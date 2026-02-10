"""
Unit Tests for SmartCheck Controller

This module contains comprehensive unit tests for the SmartCheckController class.

Test Coverage:
- SmartCheckConfig class tests
- SmartCheckController initialization tests
- Configuration management tests
- INI file operation tests
- Directory management tests
- Process control tests (with mocks)
- RunCard monitoring tests
- Thread execution tests (with mocks)
"""

import pytest
import time
import os
import configparser
import subprocess
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open

# Import the module to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from lib.testtool.smartcheck import (
    SmartCheckController,
    SmartCheckConfig,
    SmartCheckError,
    SmartCheckConfigError,
    SmartCheckTimeoutError,
    SmartCheckProcessError,
    SmartCheckRunCardError,
)


class TestSmartCheckConfig:
    """Test SmartCheckConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = SmartCheckConfig.get_default_config()
        
        assert config['total_cycle'] == 0
        assert config['total_time'] == 10080
        assert config['timeout'] == 60  # Changed to minutes
        assert config['enable_monitor_smart'] is True
        assert config['check_interval'] == 3
    
    def test_validate_config_valid(self):
        """Test validation with valid configuration."""
        config = {
            'total_cycle': 5,
            'total_time': 60,
            'timeout': 120,
        }
        
        assert SmartCheckConfig.validate_config(config) is True
    
    def test_validate_config_invalid_parameter(self):
        """Test validation with invalid parameter name."""
        config = {
            'invalid_param': 'value'
        }
        
        with pytest.raises(ValueError, match="Invalid configuration parameter"):
            SmartCheckConfig.validate_config(config)
    
    def test_validate_config_negative_cycle(self):
        """Test validation with negative cycle."""
        config = {'total_cycle': -1}
        
        with pytest.raises(ValueError, match="total_cycle must be non-negative"):
            SmartCheckConfig.validate_config(config)
    
    def test_validate_config_zero_time(self):
        """Test validation with zero or negative time."""
        config = {'total_time': 0}
        
        with pytest.raises(ValueError, match="total_time must be positive"):
            SmartCheckConfig.validate_config(config)
    
    def test_bool_conversion(self):
        """Test boolean to INI value conversion."""
        assert SmartCheckConfig.convert_bool_to_ini_value(True) == 'true'
        assert SmartCheckConfig.convert_bool_to_ini_value(False) == 'false'
        
        assert SmartCheckConfig.convert_ini_value_to_bool('true') is True
        assert SmartCheckConfig.convert_ini_value_to_bool('false') is False
        assert SmartCheckConfig.convert_ini_value_to_bool('1') is True
        assert SmartCheckConfig.convert_ini_value_to_bool('yes') is True


class TestSmartCheckController:
    """Test SmartCheckController class."""
    
    @pytest.fixture
    def test_paths(self, tmp_path):
        """Create test paths."""
        # Create dummy bat and ini files
        bat_path = tmp_path / "SmartCheck.bat"
        ini_path = tmp_path / "SmartCheck.ini"
        output_dir = tmp_path / "output"
        
        bat_path.write_text("@echo off\necho SmartCheck\n")
        ini_path.write_text("[global]\n")
        output_dir.mkdir(exist_ok=True)
        
        return {
            'bat_path': str(bat_path),
            'ini_path': str(ini_path),
            'output_dir': str(output_dir),
        }
    
    def test_init_basic(self, test_paths):
        """Test basic initialization."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        assert controller.bat_path == test_paths['bat_path']
        assert controller.cfg_ini_path == test_paths['ini_path']
        assert controller.output_dir == test_paths['output_dir']
        assert controller.status is True  # Initial status should be True
        assert controller.timeout == 60  # Now in minutes (default: 60)
        assert controller.total_cycle == 0
        assert controller.total_time == 10080
        assert controller._process is None
        assert controller._stop_event is not None
    
    def test_init_invalid_bat_path(self, test_paths):
        """Test initialization with invalid bat path."""
        with pytest.raises(SmartCheckConfigError, match="SmartCheck.bat not found"):
            SmartCheckController(
                bat_path="nonexistent.bat",
                cfg_ini_path=test_paths['ini_path'],
                output_dir=test_paths['output_dir']
            )
    
    def test_set_config(self, test_paths):
        """Test configuration setting."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        controller.set_config(
            total_time=120,
            dut_id="1",
            timeout=10,  # 10 minutes
            check_interval=5
        )
        
        assert controller.total_time == 120
        assert controller.dut_id == "1"
        assert controller.timeout == 10
        assert controller.check_interval == 5
    
    def test_set_config_invalid(self, test_paths):
        """Test configuration setting with invalid values."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        with pytest.raises(SmartCheckConfigError):
            controller.set_config(total_time=-1)
    
    def test_update_smartcheck_ini(self, test_paths):
        """Test updating SmartCheck.ini."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Update a value
        result = controller.update_smartcheck_ini('global', 'test_key', 'test_value')
        assert result is True
        
        # Verify it was written
        config = configparser.ConfigParser()
        config.read(test_paths['ini_path'])
        assert config.get('global', 'test_key') == 'test_value'
    
    def test_write_all_config_to_ini(self, test_paths):
        """Test writing all configuration to INI."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        controller.set_config(total_time=60, dut_id="2")
        controller.write_all_config_to_ini()
        
        # Verify all values written
        config = configparser.ConfigParser()
        config.read(test_paths['ini_path'])
        
        assert config.get('global', 'total_time') == '60'
        assert config.get('global', 'dut_id') == '2'
        assert config.get('global', 'output_dir') == test_paths['output_dir']
    
    def test_ensure_output_dir_exists(self, test_paths):
        """Test output directory creation."""
        new_dir = Path(test_paths['output_dir']) / "subdir" / "nested"
        
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=str(new_dir)
        )
        
        controller.ensure_output_dir_exists()
        assert new_dir.exists()
    
    def test_find_runcard_ini(self, test_paths):
        """Test finding RunCard.ini in output directory."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Create a RunCard.ini in subdirectory
        timestamp_dir = Path(test_paths['output_dir']) / "20260210130000"
        timestamp_dir.mkdir(exist_ok=True)
        runcard = timestamp_dir / "RunCard.ini"
        runcard.write_text("[Test Status]\ntest_result = ONGOING\n")
        
        # Find it
        found = controller.find_runcard_ini()
        assert found is not None
        assert found.name == "RunCard.ini"
    
    def test_read_runcard_status(self, test_paths, tmp_path):
        """Test reading RunCard.ini status."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Create a test RunCard.ini
        runcard = tmp_path / "RunCard.ini"
        runcard.write_text("""[Test Status]
version = SmiWinTools_v20251215C
test_cases = [1]
cycle = 5
loop = 0
start_time = 2026/2/10 13:00
elapsed_time = 0h10m
test_result = PASSED
err_msg = No Error
""")
        
        status = controller.read_runcard_status(runcard)
        
        assert status['version'] == 'SmiWinTools_v20251215C'
        assert status['cycle'] == 5
        assert status['test_result'] == 'PASSED'
        assert status['err_msg'] == 'No Error'
    
    def test_check_runcard_status_success(self, test_paths):
        """Test checking successful RunCard status."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Test "No Error" case
        status = {'test_result': 'ONGOING', 'err_msg': 'No Error'}
        assert controller.check_runcard_status(status) is True
        
        # Test "pass" case (case insensitive)
        status = {'test_result': 'ONGOING', 'err_msg': 'pass'}
        assert controller.check_runcard_status(status) is True
    
    def test_check_runcard_status_failure(self, test_paths):
        """Test checking failed RunCard status."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Test FAILED result
        status = {'test_result': 'FAILED', 'err_msg': 'Error occurred'}
        assert controller.check_runcard_status(status) is False
    def test_clear_output_dir(self, test_paths):
        """Test clearing output directory."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Create some test files
        test_file = Path(test_paths['output_dir']) / "test.txt"
        test_subdir = Path(test_paths['output_dir']) / "subdir"
        test_subdir.mkdir(exist_ok=True)
        test_file.write_text("test content")
        (test_subdir / "file.txt").write_text("test")
        
        # Clear directory
        controller.clear_output_dir()
        
        # Verify directory is empty but still exists
        assert Path(test_paths['output_dir']).exists()
        assert len(list(Path(test_paths['output_dir']).iterdir())) == 0
    
    def test_load_config_from_json(self, test_paths, tmp_path):
        """Test loading configuration from JSON file."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Create a JSON config file
        json_config = {
            "smartcheck": {
                "total_time": 30,
                "dut_id": "5",
                "timeout": 15,
                "total_cycle": 10
            }
        }
        json_path = tmp_path / "config.json"
        json_path.write_text(json.dumps(json_config))
        
        # Load configuration
        controller.load_config_from_json(str(json_path))
        
        # Verify configuration was loaded
        assert controller.total_time == 30
        assert controller.dut_id == "5"
        assert controller.timeout == 15
        assert controller.total_cycle == 10
    
    def test_load_config_from_json_missing_section(self, test_paths, tmp_path):
        """Test loading JSON without 'smartcheck' section."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        json_config = {"other": {}}
        json_path = tmp_path / "config.json"
        json_path.write_text(json.dumps(json_config))
        
        with pytest.raises(SmartCheckConfigError, match="'smartcheck' section not found"):
            controller.load_config_from_json(str(json_path))
    
    def test_load_config_from_json_invalid_file(self, test_paths):
        """Test loading from non-existent JSON file."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        with pytest.raises(SmartCheckConfigError, match="not found"):
            controller.load_config_from_json("nonexistent.json")


class TestSmartCheckControllerProcessControl:
    """Test process control methods with mocks."""
    
    @pytest.fixture
    def test_paths(self, tmp_path):
        """Create test paths."""
        bat_path = tmp_path / "SmartCheck.bat"
        ini_path = tmp_path / "SmartCheck.ini"
        output_dir = tmp_path / "output"
        
        bat_path.write_text("@echo off\necho SmartCheck\n")
        ini_path.write_text("[global]\n")
        output_dir.mkdir(exist_ok=True)
        
        return {
            'bat_path': str(bat_path),
            'ini_path': str(ini_path),
            'output_dir': str(output_dir),
        }
    
    @patch('subprocess.Popen')
    def test_start_smartcheck_bat(self, mock_popen, test_paths):
        """Test starting SmartCheck.bat process."""
        # Setup mock process
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Start the process
        result = controller.start_smartcheck_bat()
        
        # Verify
        assert result is True
        assert controller._process is not None
        assert controller._process.pid == 12345
        mock_popen.assert_called_once()
    
    @patch('subprocess.Popen')
    def test_start_smartcheck_bat_immediate_exit(self, mock_popen, test_paths):
        """Test starting SmartCheck.bat that exits immediately."""
        # Setup mock process that exits immediately
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process exited
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Should raise exception
        with pytest.raises(SmartCheckProcessError, match="terminated immediately"):
            controller.start_smartcheck_bat()
    
    def test_stop_smartcheck_bat_no_process(self, test_paths):
        """Test stopping when no process is running."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Should not raise exception
        controller.stop_smartcheck_bat()
        assert controller._process is None
    
    @patch('subprocess.run')
    def test_stop_smartcheck_bat_graceful(self, mock_run, test_paths):
        """Test graceful process termination."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Setup mock process
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Running
        mock_process.pid = 12345
        controller._process = mock_process
        
        # Stop the process
        controller.stop_smartcheck_bat(force=False)
        
        # Verify terminate was called
        mock_process.terminate.assert_called_once()
        assert controller._process is None
    
    @patch('subprocess.run')
    def test_stop_smartcheck_bat_force(self, mock_run, test_paths):
        """Test force process termination."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Setup mock process
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 12345
        controller._process = mock_process
        
        # Force stop
        controller.stop_smartcheck_bat(force=True)
        
        # Verify kill was called
        mock_process.kill.assert_called_once()
        assert controller._process is None


class TestSmartCheckControllerRunCardMonitoring:
    """Test RunCard.ini monitoring methods."""
    
    @pytest.fixture
    def test_paths(self, tmp_path):
        """Create test paths."""
        bat_path = tmp_path / "SmartCheck.bat"
        ini_path = tmp_path / "SmartCheck.ini"
        output_dir = tmp_path / "output"
        
        bat_path.write_text("@echo off\n")
        ini_path.write_text("[global]\n")
        output_dir.mkdir(exist_ok=True)
        
        return {
            'bat_path': str(bat_path),
            'ini_path': str(ini_path),
            'output_dir': str(output_dir),
        }
    
    def test_find_runcard_ini_not_found(self, test_paths):
        """Test finding RunCard.ini when it doesn't exist."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        result = controller.find_runcard_ini()
        assert result is None
    
    def test_find_runcard_ini_in_subdirectory(self, test_paths):
        """Test finding RunCard.ini in timestamp subdirectory."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Create RunCard.ini in subdirectory
        timestamp_dir = Path(test_paths['output_dir']) / "20260210150000"
        timestamp_dir.mkdir(exist_ok=True)
        runcard = timestamp_dir / "RunCard.ini"
        runcard.write_text("[Test Status]\ntest_result = ONGOING\n")
        
        result = controller.find_runcard_ini()
        
        assert result is not None
        assert result.name == "RunCard.ini"
        assert result.parent.name == "20260210150000"
    
    def test_find_runcard_ini_multiple_files(self, test_paths):
        """Test finding most recent RunCard.ini when multiple exist."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Create multiple RunCard.ini files
        old_dir = Path(test_paths['output_dir']) / "20260210100000"
        old_dir.mkdir(exist_ok=True)
        old_runcard = old_dir / "RunCard.ini"
        old_runcard.write_text("[Test Status]\n")
        
        time.sleep(0.1)  # Ensure different timestamps
        
        new_dir = Path(test_paths['output_dir']) / "20260210150000"
        new_dir.mkdir(exist_ok=True)
        new_runcard = new_dir / "RunCard.ini"
        new_runcard.write_text("[Test Status]\n")
        
        result = controller.find_runcard_ini()
        
        # Should return the most recent one
        assert result is not None
        assert result.parent.name == "20260210150000"
    
    def test_read_runcard_status_all_fields(self, test_paths, tmp_path):
        """Test reading all fields from RunCard.ini."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Create comprehensive RunCard.ini
        runcard = tmp_path / "RunCard.ini"
        runcard.write_text("""[Test Status]
version = SmiWinTools_v20251215C
test_cases = [1]
cycle = 10
loop = 2
start_time = 2026/2/10 15:00
elapsed_time = 1h30m
test_result = ONGOING
err_msg = No Error
""")
        
        status = controller.read_runcard_status(runcard)
        
        assert status['version'] == 'SmiWinTools_v20251215C'
        assert status['test_cases'] == '[1]'
        assert status['cycle'] == 10
        assert status['loop'] == 2
        assert status['start_time'] == '2026/2/10 15:00'
        assert status['elapsed_time'] == '1h30m'
        assert status['test_result'] == 'ONGOING'
        assert status['err_msg'] == 'No Error'
    
    def test_read_runcard_status_missing_section(self, test_paths, tmp_path):
        """Test reading RunCard.ini without [Test Status] section."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        runcard = tmp_path / "RunCard.ini"
        runcard.write_text("[Other Section]\nkey = value\n")
        
        with pytest.raises(SmartCheckRunCardError, match="Test Status.*section not found"):
            controller.read_runcard_status(runcard)
    
    def test_check_runcard_status_ongoing_no_error(self, test_paths):
        """Test checking status with ONGOING and No Error."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        status = {
            'test_result': 'ONGOING',
            'err_msg': 'No Error'
        }
        
        assert controller.check_runcard_status(status) is True
    
    def test_check_runcard_status_pass_case_insensitive(self, test_paths):
        """Test checking status with 'pass' (case insensitive)."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        # Test different cases
        for msg in ['pass', 'PASS', 'Pass', 'pAsS']:
            status = {'test_result': 'ONGOING', 'err_msg': msg}
            assert controller.check_runcard_status(status) is True
    
    def test_check_runcard_status_failed_result(self, test_paths):
        """Test checking status with FAILED result."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        status = {
            'test_result': 'FAILED',
            'err_msg': 'Test failed'
        }
        
        assert controller.check_runcard_status(status) is False
    
    def test_check_runcard_status_error_message(self, test_paths):
        """Test checking status with error message."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        status = {
            'test_result': 'ONGOING',
            'err_msg': 'Some error occurred'
        }
        
        assert controller.check_runcard_status(status) is False


class TestSmartCheckControllerThreadExecution:
    """Test thread execution with mocks."""
    
    @pytest.fixture
    def test_paths(self, tmp_path):
        """Create test paths."""
        bat_path = tmp_path / "SmartCheck.bat"
        ini_path = tmp_path / "SmartCheck.ini"
        output_dir = tmp_path / "output"
        
        bat_path.write_text("@echo off\n")
        ini_path.write_text("[global]\n")
        output_dir.mkdir(exist_ok=True)
        
        return {
            'bat_path': str(bat_path),
            'ini_path': str(ini_path),
            'output_dir': str(output_dir),
        }
    
    def test_stop_event(self, test_paths):
        """Test stop event functionality."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        
        assert not controller._stop_event.is_set()
        
        controller.stop()
        
        assert controller._stop_event.is_set()
    
    @patch.object(SmartCheckController, 'start_smartcheck_bat')
    @patch.object(SmartCheckController, 'stop_smartcheck_bat')
    @patch.object(SmartCheckController, 'find_runcard_ini')
    def test_run_timeout(self, mock_find, mock_stop, mock_start, test_paths):
        """Test run method with timeout."""
        controller = SmartCheckController(
            bat_path=test_paths['bat_path'],
            cfg_ini_path=test_paths['ini_path'],
            output_dir=test_paths['output_dir']
        )
        controller.timeout = 0.01  # Very short timeout (0.01 minutes = 0.6 seconds)
        
        # Mock methods
        mock_start.return_value = True
        mock_find.return_value = None  # Never find RunCard.ini
        
        # Run in thread
        controller.start()
        controller.join(timeout=5)
        
        # Should timeout and set status to False
        assert controller.status is False
        mock_start.assert_called_once()
        mock_stop.assert_called_once()


        
        # Test error message
        status = {'test_result': 'ONGOING', 'err_msg': 'Some error'}
        assert controller.check_runcard_status(status) is False


@pytest.mark.integration
class TestSmartCheckControllerIntegration:
    """Integration tests requiring actual SmartCheck.bat."""
    
    def test_full_workflow(self):
        """
        Test complete workflow with real SmartCheck.bat.
        
        Note: This test requires actual SmartCheck.bat and may take several minutes.
        """
        # This is a placeholder for integration tests
        # Actual implementation would use real paths
        pytest.skip("Integration test requires actual SmartCheck.bat")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
