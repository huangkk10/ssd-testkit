"""
SmartCheck Controller

Threading-based controller for managing SmartCheck.bat execution and monitoring.

This module provides the main SmartCheckController class that:
- Manages SmartCheck.bat process lifecycle
- Configures SmartCheck.ini parameters
- Monitors RunCard.ini for test status
- Provides thread-safe execution control
"""

import threading
import subprocess
import time
import os
import json
import configparser
import shutil
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.logger import LogEvt, LogErr, LogWarn, LogDebug, logConfig
from .config import SmartCheckConfig
from .exceptions import (
    SmartCheckConfigError,
    SmartCheckTimeoutError,
    SmartCheckProcessError,
    SmartCheckRunCardError,
)

# Initialize logger configuration
try:
    logConfig()
except Exception:
    # If logger setup fails, fall back to basic logging
    pass


class SmartCheckController(threading.Thread):
    """
    SmartCheck controller for managing SmartCheck.bat execution.
    
    This class inherits from threading.Thread and provides comprehensive
    control over SmartCheck.bat including:
    - Configuration management for SmartCheck.ini
    - Process control (start/stop)
    - Status monitoring through RunCard.ini
    - Automatic error detection and timeout handling
    
    Attributes:
        bat_path (str): Relative path to SmartCheck.bat
        cfg_ini_path (str): Relative path to SmartCheck.ini
        output_dir (str): Absolute path to output directory
        total_cycle (int): Total number of test cycles (0 = infinite)
        total_time (int): Total test time in minutes
        dut_id (str): Device Under Test identifier
        enable_monitor_smart (bool): Enable SMART monitoring
        close_window_when_failed (bool): Close console on failure
        stop_when_failed (bool): Stop execution on failure
        smart_config_file (str): Path to SMART configuration file
        timeout (int): Maximum execution time in minutes
        check_interval (int): Status check interval in seconds
        status (bool): Execution status (True=success, False=failure)
    
    Example:
        >>> controller = SmartCheckController(
        ...     bat_path="./bin/SmiWinTools/SmartCheck.bat",
        ...     cfg_ini_path="./bin/SmiWinTools/SmartCheck.ini",
        ...     output_dir="./test_output"
        ... )
        >>> controller.set_config(total_time=60, dut_id="0")
        >>> controller.start()
        >>> controller.join(timeout=120)
        >>> print(controller.status)
        True
    """
    
    def __init__(
        self,
        bat_path: str,
        cfg_ini_path: str,
        output_dir: str,
        **kwargs
    ):
        """
        Initialize SmartCheck controller.
        
        Args:
            bat_path: Relative path to SmartCheck.bat
            cfg_ini_path: Relative path to SmartCheck.ini
            output_dir: Absolute path to output directory
            **kwargs: Additional configuration parameters (optional)
                - total_cycle: Total test cycles
                - total_time: Total test time in minutes
                - dut_id: Device Under Test ID
                - timeout: Execution timeout in minutes
                - check_interval: Status check interval in seconds
                - etc.
        
        Raises:
            SmartCheckConfigError: If required paths are invalid
        """
        super().__init__()
        
        # Validate and store paths
        self.bat_path = bat_path
        self.cfg_ini_path = cfg_ini_path
        self.output_dir = output_dir
        
        # Validate bat_path and cfg_ini_path exist
        if not os.path.exists(self.bat_path):
            LogErr(f"SmartCheck.bat not found at: {self.bat_path}")
            raise SmartCheckConfigError(f"SmartCheck.bat not found at: {self.bat_path}")
        if not os.path.exists(self.cfg_ini_path):
            LogErr(f"SmartCheck.ini not found at: {self.cfg_ini_path}")
            raise SmartCheckConfigError(f"SmartCheck.ini not found at: {self.cfg_ini_path}")
        
        # Load default configuration
        default_config = SmartCheckConfig.get_default_config()
        
        # Set SmartCheck.ini [global] section parameters
        self.total_cycle: int = default_config['total_cycle']
        self.total_time: int = default_config['total_time']
        self.dut_id: str = default_config['dut_id']
        self.enable_monitor_smart: bool = default_config['enable_monitor_smart']
        self.close_window_when_failed: bool = default_config['close_window_when_failed']
        self.stop_when_failed: bool = default_config['stop_when_failed']
        self.smart_config_file: str = default_config['smart_config_file']
        
        # Execution control parameters
        self.timeout: int = default_config['timeout']
        self.check_interval: int = default_config['check_interval']
        self.status: bool = True  # True = success, False = failure
        
        # Internal state management
        self._process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._runcard_path: Optional[Path] = None
        
        # Apply any additional configuration from kwargs
        if kwargs:
            self.set_config(**kwargs)
        
        LogEvt(f"SmartCheckController initialized with bat_path={bat_path}, output_dir={output_dir}")
    
    def load_config_from_json(self, json_path: str) -> None:
        """
        Load configuration from JSON file.
        
        Expected JSON format:
        {
            "smartcheck": {
                "output_dir": "/path/to/output",
                "total_cycle": 0,
                "total_time": 10080,
                "dut_id": "0",
                "enable_monitor_smart": true,
                "stop_when_failed": true,
                "timeout": 3600
            }
        }
        
        Args:
            json_path: Path to JSON configuration file
        
        Raises:
            SmartCheckConfigError: If JSON file is invalid or missing
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract smartcheck configuration section
            if 'smartcheck' not in data:
                raise SmartCheckConfigError(f"'smartcheck' section not found in {json_path}")
            
            config = data['smartcheck']
            
            # Validate and apply configuration
            SmartCheckConfig.validate_config(config)
            self.set_config(**config)
            
            LogEvt(f"Configuration loaded from {json_path}")
            
        except FileNotFoundError:
            raise SmartCheckConfigError(f"JSON configuration file not found: {json_path}")
        except json.JSONDecodeError as e:
            raise SmartCheckConfigError(f"Invalid JSON format in {json_path}: {e}")
        except Exception as e:
            raise SmartCheckConfigError(f"Failed to load configuration: {e}")
    
    def set_config(self, **kwargs) -> None:
        """
        Set configuration parameters directly.
        
        This method allows dynamic configuration of controller parameters.
        Parameters are validated before being applied.
        
        Args:
            **kwargs: Configuration parameters as keyword arguments
        
        Raises:
            SmartCheckConfigError: If invalid parameters are provided
        
        Example:
            >>> controller.set_config(total_time=60, dut_id="1", timeout=120)
        """
        try:
            # Validate configuration first
            SmartCheckConfig.validate_config(kwargs)
            
            # Apply each configuration parameter
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                    LogDebug(f"Configuration updated: {key}={value}")
                else:
                    LogWarn(f"Unknown configuration parameter ignored: {key}")
            
        except ValueError as e:
            raise SmartCheckConfigError(f"Invalid configuration: {e}")
    
    @classmethod
    def from_config_dict(cls, config_dict: dict, bat_path_key: str = 'bat_path', 
                        output_dir_key: str = 'output_dir'):
        """
        Create SmartCheckController from a configuration dictionary.
        
        This is a convenience factory method that simplifies initialization
        from Config.json or similar configuration sources.
        
        Args:
            config_dict: Configuration dictionary containing SmartCheck parameters
            bat_path_key: Key name for bat_path (default: 'bat_path')
            output_dir_key: Key name for output_dir (default: 'output_dir')
        
        Returns:
            SmartCheckController: Configured controller instance
        
        Raises:
            SmartCheckConfigError: If required keys are missing or invalid
        
        Example:
            >>> config = {
            ...     "bat_path": "./bin/SmiWinTools/SmartCheck.bat",
            ...     "output_dir": "./testlog/SmartLog",
            ...     "total_time": 10080,
            ...     "dut_id": "1"
            ... }
            >>> controller = SmartCheckController.from_config_dict(config)
        """
        # Extract required parameters
        bat_path = config_dict.get(bat_path_key)
        output_dir = config_dict.get(output_dir_key)
        
        if not bat_path:
            raise SmartCheckConfigError(f"Required key '{bat_path_key}' not found in config")
        if not output_dir:
            raise SmartCheckConfigError(f"Required key '{output_dir_key}' not found in config")
        
        # Derive cfg_ini_path from bat_path (replace .bat with .ini)
        cfg_ini_path = os.path.splitext(bat_path)[0] + '.ini'
        
        # Create controller instance
        controller = cls(
            bat_path=bat_path,
            cfg_ini_path=cfg_ini_path,
            output_dir=output_dir
        )
        
        # Apply optional parameters
        optional_params = [
            'total_cycle', 'total_time', 'dut_id', 'timeout',
            'check_interval', 'enable_monitor_smart', 'close_window_when_failed',
            'stop_when_failed', 'smart_config_file'
        ]
        
        kwargs = {}
        for param in optional_params:
            if param in config_dict:
                kwargs[param] = config_dict[param]
        
        if kwargs:
            controller.set_config(**kwargs)
        
        LogEvt(f"SmartCheckController created from config dict: {bat_path}")
        return controller
    
    def update_smartcheck_ini(self, section: str, key: str, value: str) -> bool:
        """
        Update a specific key in SmartCheck.ini.
        
        This method reads the INI file, updates the specified key,
        and writes it back to disk.
        
        Args:
            section: INI section name (e.g., 'global')
            key: Configuration key name
            value: New value to set
        
        Returns:
            True if update was successful, False otherwise
        
        Raises:
            SmartCheckConfigError: If INI file cannot be read or written
        
        Example:
            >>> controller.update_smartcheck_ini('global', 'output_dir', '/path/to/output')
            True
        """
        try:
            config = configparser.ConfigParser()
            config.read(self.cfg_ini_path, encoding='utf-8')
            
            # Create section if it doesn't exist
            if not config.has_section(section):
                config.add_section(section)
            
            # Update the key
            config.set(section, key, str(value))
            
            # Write back to file
            with open(self.cfg_ini_path, 'w', encoding='utf-8') as f:
                config.write(f)
            
            LogDebug(f"Updated SmartCheck.ini: [{section}] {key}={value}")
            return True
            
        except Exception as e:
            LogErr(f"Failed to update SmartCheck.ini: {e}")
            raise SmartCheckConfigError(f"Failed to update INI file: {e}")
    
    def write_all_config_to_ini(self) -> bool:
        """
        Write all current configuration to SmartCheck.ini.
        
        This method writes all controller parameters to the [global]
        section of SmartCheck.ini, ensuring consistency between
        controller state and INI file.
        
        Returns:
            True if successful, False otherwise
        
        Raises:
            SmartCheckConfigError: If INI file cannot be written
        """
        try:
            config = configparser.ConfigParser()
            config.read(self.cfg_ini_path, encoding='utf-8')
            
            # Ensure [global] section exists
            if not config.has_section('global'):
                config.add_section('global')
            
            # Convert output_dir to absolute path before writing to INI
            # SmartCheck.bat runs in its own directory, so relative paths won't work
            abs_output_dir = os.path.abspath(self.output_dir)
            
            # Write all SmartCheck.ini parameters
            config.set('global', 'output_dir', abs_output_dir)
            config.set('global', 'total_cycle', str(self.total_cycle))
            config.set('global', 'total_time', str(self.total_time))
            config.set('global', 'dut_id', str(self.dut_id))
            config.set('global', 'enable_monitor_smart', 
                      SmartCheckConfig.convert_bool_to_ini_value(self.enable_monitor_smart))
            config.set('global', 'close_window_when_failed', 
                      SmartCheckConfig.convert_bool_to_ini_value(self.close_window_when_failed))
            config.set('global', 'stop_when_failed', 
                      SmartCheckConfig.convert_bool_to_ini_value(self.stop_when_failed))
            config.set('global', 'smart_config_file', self.smart_config_file)
            
            # Write to file
            with open(self.cfg_ini_path, 'w', encoding='utf-8') as f:
                config.write(f)
            
            LogEvt("All configuration written to SmartCheck.ini")
            return True
            
        except Exception as e:
            LogErr(f"Failed to write configuration to INI: {e}")
            raise SmartCheckConfigError(f"Failed to write INI file: {e}")
    
    def clear_output_dir(self) -> None:
        """
        Clear all files and subdirectories in output_dir.
        
        This method removes all contents of the output directory
        while preserving the directory itself. Useful for ensuring
        clean test runs.
        
        IMPORTANT:
            - Also clears SmartCheck.bat's default log directory if it exists
            - Validates paths to prevent accidental deletion of system directories
        
        Note:
            - Directory itself is preserved
            - Handles file permission errors gracefully
            - Logs all deletion operations
        
        Raises:
            OSError: If files cannot be deleted (may be logged instead)
        """
        # Validate output_dir is safe to clear
        if not self.output_dir or self.output_dir.strip() == '':
            LogWarn("Output directory is empty, skipping clear")
            return
        
        # Convert to absolute path and validate
        abs_output_dir = os.path.abspath(self.output_dir)
        
        # Safety check: don't clear root directories or system directories
        dangerous_paths = ['/', 'C:\\', 'C:\\Windows', 'C:\\Program Files', 
                          'C:\\Program Files (x86)', os.path.expanduser('~')]
        if abs_output_dir in dangerous_paths or len(abs_output_dir) <= 3:
            LogErr(f"Refusing to clear dangerous path: {abs_output_dir}")
            raise SmartCheckConfigError(f"Cannot clear dangerous path: {abs_output_dir}")
        
        # Clear the configured output directory
        if os.path.exists(abs_output_dir):
            try:
                LogDebug(f"Clearing configured output directory: {abs_output_dir}")
                self._clear_directory_contents(abs_output_dir)
                LogEvt(f"Cleared configured output directory: {abs_output_dir}")
            except Exception as e:
                LogErr(f"Error clearing configured output directory: {e}")
        else:
            LogDebug(f"Configured output directory does not exist: {abs_output_dir}")
        
        # Also clear SmartCheck.bat's default log directory if it exists
        # Default is: <SmartCheck.bat directory>/log_SmartCheck/
        bat_dir = os.path.dirname(os.path.abspath(self.bat_path))
        default_log_dir = os.path.join(bat_dir, 'log_SmartCheck')
        
        if os.path.exists(default_log_dir) and default_log_dir != abs_output_dir:
            try:
                LogDebug(f"Clearing default SmartCheck log directory: {default_log_dir}")
                self._clear_directory_contents(default_log_dir)
                LogEvt(f"Cleared default log directory: {default_log_dir}")
            except Exception as e:
                LogWarn(f"Failed to clear default log directory: {e}")
    
    def _clear_directory_contents(self, directory: str) -> None:
        """
        Internal method to clear contents of a directory.
        
        Args:
            directory: Absolute path to directory to clear
        """
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                        LogDebug(f"Deleted file: {item_path}")
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        LogDebug(f"Deleted directory: {item_path}")
                except Exception as e:
                    LogWarn(f"Failed to delete {item_path}: {e}")
        except Exception as e:
            LogErr(f"Error listing directory {directory}: {e}")
            raise
    
    def ensure_output_dir_exists(self) -> None:
        """
        Ensure output directory exists, create if necessary.
        
        This method creates the output directory and all parent
        directories if they don't exist.
        """
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            LogDebug(f"Output directory ensured: {self.output_dir}")
        except Exception as e:
            LogErr(f"Failed to create output directory: {e}")
            raise SmartCheckConfigError(f"Cannot create output directory: {e}")
    
    def start_smartcheck_bat(self) -> bool:
        """
        Start SmartCheck.bat process.
        
        This method:
        1. Writes current configuration to SmartCheck.ini
        2. Launches SmartCheck.bat in a new console window
        3. Stores the process handle for later control
        
        Returns:
            True if process started successfully, False otherwise
        
        Raises:
            SmartCheckProcessError: If process cannot be started
        """
        try:
            # Write configuration before starting
            self.write_all_config_to_ini()
            
            # Ensure output directory exists
            self.ensure_output_dir_exists()
            
            # Get absolute path to bat file
            bat_abs_path = os.path.abspath(self.bat_path)
            bat_dir = os.path.dirname(bat_abs_path)
            
            LogEvt(f"Starting SmartCheck.bat: {bat_abs_path}")
            
            # Start process in new console window
            # CREATE_NEW_CONSOLE allows SmartCheck to run in separate window
            # Note: Do NOT use stdout=PIPE/stderr=PIPE with CREATE_NEW_CONSOLE
            #       as it will capture output and leave the window blank
            self._process = subprocess.Popen(
                [bat_abs_path],
                cwd=bat_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            # Give process a moment to start
            time.sleep(1)
            
            # Check if process started successfully
            if self._process.poll() is not None:
                # Process already terminated
                raise SmartCheckProcessError(f"SmartCheck.bat terminated immediately with code {self._process.returncode}")
            
            LogEvt(f"SmartCheck.bat started successfully (PID: {self._process.pid})")
            return True
            
        except Exception as e:
            LogErr(f"Failed to start SmartCheck.bat: {e}")
            raise SmartCheckProcessError(f"Cannot start SmartCheck.bat: {e}")
    
    def stop_smartcheck_bat(self, force: bool = False) -> None:
        """
        Stop SmartCheck.bat process.
        
        This method attempts graceful termination first, then
        forces termination if necessary.
        
        Args:
            force: If True, use kill() instead of terminate()
        
        Note:
            - Tries terminate() first
            - Falls back to kill() if terminate fails
            - Uses taskkill on Windows for stubborn processes
            - Cleans up process handle after termination
        """
        if self._process is None:
            LogDebug("No process to stop")
            return
        
        try:
            # Check if process is still running
            if self._process.poll() is not None:
                LogEvt(f"Process already terminated with code {self._process.returncode}")
                self._process = None
                return
            
            pid = self._process.pid
            LogEvt(f"Stopping SmartCheck.bat (PID: {pid})")
            
            if force:
                # Force kill
                self._process.kill()
                LogEvt("Process killed forcefully")
            else:
                # Try graceful termination first
                self._process.terminate()
                LogEvt("Terminate signal sent")
                
                # Wait for process to terminate (up to 5 seconds)
                try:
                    self._process.wait(timeout=5)
                    LogEvt("Process terminated gracefully")
                except subprocess.TimeoutExpired:
                    LogWarn("Graceful termination timeout, forcing kill")
                    self._process.kill()
                    self._process.wait(timeout=2)
            
            # Additional cleanup using taskkill on Windows
            # This helps kill any child processes
            try:
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(pid)],
                    capture_output=True,
                    timeout=3
                )
                LogDebug("Additional cleanup with taskkill completed")
            except Exception as e:
                LogDebug(f"taskkill cleanup failed (may be normal): {e}")
            
        except Exception as e:
            LogErr(f"Error stopping process: {e}")
        finally:
            self._process = None
            LogEvt("SmartCheck.bat process stopped")
    
    def find_runcard_ini(self) -> Optional[Path]:
        """
        Find RunCard.ini in output directory.
        
        SmartCheck.bat creates subdirectories with timestamp format
        (YYYYMMDDHHMMSS). This method recursively searches for
        RunCard.ini and returns the path to the most recent one.
        
        Returns:
            Path to RunCard.ini if found, None otherwise
        
        Note:
            - Searches output_dir recursively
            - Returns first match found
            - Caches result in self._runcard_path for efficiency
        """
        # Return cached path if already found
        if self._runcard_path and self._runcard_path.exists():
            return self._runcard_path
        
        if not os.path.exists(self.output_dir):
            LogDebug(f"Output directory does not exist: {self.output_dir}")
            return None
        
        try:
            # Search recursively for RunCard.ini
            # SmartCheck.bat typically creates: output_dir/YYYYMMDDHHMMSS/RunCard.ini
            found_paths = []
            for root, dirs, files in os.walk(self.output_dir):
                if 'RunCard.ini' in files:
                    runcard_path = Path(root) / 'RunCard.ini'
                    found_paths.append(runcard_path)
                    LogDebug(f"Found RunCard.ini at: {runcard_path}")
            
            if not found_paths:
                return None
            
            # If multiple found, return the most recently modified
            if len(found_paths) > 1:
                found_paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                LogDebug(f"Multiple RunCard.ini found, using most recent: {found_paths[0]}")
            
            # Cache the path
            self._runcard_path = found_paths[0]
            return self._runcard_path
            
        except Exception as e:
            LogErr(f"Error searching for RunCard.ini: {e}")
            return None
    
    def read_runcard_status(self, runcard_path: Path) -> Dict[str, Any]:
        """
        Read status information from RunCard.ini.
        
        Parses the [Test Status] section of RunCard.ini and
        returns structured status information.
        
        Args:
            runcard_path: Path to RunCard.ini file
        
        Returns:
            Dictionary containing:
                - version: SmiWinTools version
                - test_cases: Test cases list
                - cycle: Current cycle number
                - loop: Current loop number
                - start_time: Test start time
                - elapsed_time: Elapsed time
                - test_result: ONGOING/PASSED/FAILED
                - err_msg: Error message or "No Error"
        
        Raises:
            SmartCheckRunCardError: If file cannot be read or parsed
        
        Example:
            >>> status = controller.read_runcard_status(Path("RunCard.ini"))
            >>> print(status['test_result'])
            'PASSED'
        """
        try:
            config = configparser.ConfigParser()
            config.read(runcard_path, encoding='utf-8')
            
            if not config.has_section('Test Status'):
                raise SmartCheckRunCardError(f"[Test Status] section not found in {runcard_path}")
            
            # Extract all status fields
            status_dict = {
                'version': config.get('Test Status', 'version', fallback=''),
                'test_cases': config.get('Test Status', 'test_cases', fallback=''),
                'cycle': config.getint('Test Status', 'cycle', fallback=0),
                'loop': config.getint('Test Status', 'loop', fallback=0),
                'start_time': config.get('Test Status', 'start_time', fallback=''),
                'elapsed_time': config.get('Test Status', 'elapsed_time', fallback=''),
                'test_result': config.get('Test Status', 'test_result', fallback='ONGOING'),
                'err_msg': config.get('Test Status', 'err_msg', fallback='No Error'),
            }
            
            LogDebug(f"RunCard status: {status_dict['test_result']}, cycle: {status_dict['cycle']}, err_msg: {status_dict['err_msg']}")
            return status_dict
            
        except configparser.Error as e:
            raise SmartCheckRunCardError(f"Failed to parse RunCard.ini: {e}")
        except Exception as e:
            raise SmartCheckRunCardError(f"Error reading RunCard.ini: {e}")
    
    def check_runcard_status(self, status_dict: Dict[str, Any]) -> bool:
        """
        Check if RunCard status indicates success.
        
        This method evaluates the status dictionary and determines
        if the test is proceeding successfully.
        
        Args:
            status_dict: Dictionary from read_runcard_status()
        
        Returns:
            True if status is normal (no errors), False otherwise
        
        Logic:
            - err_msg check (case-insensitive):
                - "no error" → True
                - "pass" → True
                - anything else → False
            - test_result check:
                - "FAILED" → False
        """
        # Check test_result first
        test_result = status_dict.get('test_result', '').upper()
        if test_result == 'FAILED':
            LogWarn(f"Test result is FAILED")
            return False
        
        # Check error message (case-insensitive)
        err_msg = status_dict.get('err_msg', '').lower().strip()
        
        # "no error" or "pass" indicates success
        if err_msg in ['no error', 'pass', '']:
            return True
        
        # Any other error message indicates failure
        LogWarn(f"Error detected in RunCard: {status_dict.get('err_msg')}")
        return False
    
    def run(self) -> None:
        """
        Main thread execution method.
        
        This is the entry point when start() is called on the controller.
        It implements the complete workflow:
        
        1. Preparation Phase:
           - Write configuration to SmartCheck.ini
           - Create output directory
           - Start SmartCheck.bat
        
        2. Monitoring Phase (loop until complete/timeout/error):
           - Check for stop signal
           - Search for RunCard.ini
           - Read and validate status
           - Check for errors
           - Check for timeout
           - Wait check_interval seconds
        
        3. Cleanup Phase:
           - Stop SmartCheck.bat process
           - Set final status
           - Log completion
        
        Note:
            - Sets self.status to False on any error
            - Handles timeout gracefully
            - Ensures process cleanup even on exceptions
        """
        start_time = time.time()
        LogEvt("SmartCheckController thread started")
        
        # Convert timeout from minutes to seconds for internal use
        timeout_seconds = self.timeout * 60
        
        try:
            # ===== Phase 1: Preparation =====
            LogEvt("Phase 1: Preparation")
            
            # Write configuration to SmartCheck.ini FIRST
            # This ensures output_dir is set before clearing
            self.write_all_config_to_ini()
            
            # Ensure output directory exists
            self.ensure_output_dir_exists()
            
            # Clear output directory for clean test run
            # This must happen AFTER write_all_config_to_ini()
            # to ensure we're clearing the correct directory
            self.clear_output_dir()
            
            # Start SmartCheck.bat
            self.start_smartcheck_bat()
            
            LogEvt(f"SmartCheck.bat started, monitoring for {self.timeout} minutes ({timeout_seconds} seconds)...")
            
            # ===== Phase 2: Monitoring Loop =====
            LogEvt("Phase 2: Monitoring")
            
            # Track when we started SmartCheck.bat for RunCard.ini timeout
            smartcheck_start_time = time.time()
            runcard_timeout = 300  # 5 minutes (300 seconds) to find RunCard.ini
            
            while not self._stop_event.is_set():
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    LogErr(f"Timeout reached ({self.timeout} minutes / {timeout_seconds}s), stopping SmartCheck")
                    self.status = False
                    break
                
                # Search for RunCard.ini
                runcard_path = self.find_runcard_ini()
                if not runcard_path:
                    # RunCard.ini not yet created, wait and retry
                    elapsed_since_start = time.time() - smartcheck_start_time
                    LogDebug(f"RunCard.ini not found yet, waiting... ({elapsed_since_start:.1f}s since start)")
                    
                    # Check if we've exceeded the 5-minute timeout for finding RunCard.ini
                    if elapsed_since_start > runcard_timeout:
                        LogErr(f"RunCard.ini not found within {runcard_timeout}s (5 minutes), stopping SmartCheck")
                        self.status = False
                        break
                    
                    time.sleep(self.check_interval)
                    continue
                
                # Read RunCard status
                try:
                    status_dict = self.read_runcard_status(runcard_path)
                except SmartCheckRunCardError as e:
                    LogWarn(f"Failed to read RunCard.ini: {e}")
                    time.sleep(self.check_interval)
                    continue
                
                # Check if status is normal
                if not self.check_runcard_status(status_dict):
                    LogErr(f"Error detected in RunCard: {status_dict.get('err_msg')}")
                    self.status = False
                    break
                
                # Check if test completed
                test_result = status_dict.get('test_result', '').upper()
                if test_result == 'PASSED':
                    LogEvt("SmartCheck completed successfully (PASSED)")
                    self.status = True
                    break
                elif test_result == 'FAILED':
                    LogErr("SmartCheck failed (FAILED)")
                    self.status = False
                    break
                
                # Test still ongoing, continue monitoring
                LogDebug(f"Status: {test_result}, Cycle: {status_dict.get('cycle')}, Elapsed: {elapsed:.1f}s")
                time.sleep(self.check_interval)
            
            # Check if stopped by user request
            if self._stop_event.is_set():
                LogEvt("SmartCheck stopped by user request")
                # Don't set status to False - it should reflect actual test state
                # If status is still None, it means test was stopped before completion
                # If status is True/False, keep that value
                pass
            
        except SmartCheckProcessError as e:
            LogErr(f"Process error: {e}")
            self.status = False
        except SmartCheckConfigError as e:
            LogErr(f"Configuration error: {e}")
            self.status = False
        except Exception as e:
            LogErr(f"Unexpected error in SmartCheck thread: {e}", exc_info=True)
            self.status = False
        finally:
            # ===== Phase 3: Cleanup =====
            LogEvt("Phase 3: Cleanup")
            
            # Always stop the process
            self.stop_smartcheck_bat()
            
            elapsed_total = time.time() - start_time
            LogEvt(f"SmartCheckController thread finished (Status: {self.status}, Duration: {elapsed_total:.1f}s)")
    
    def stop(self) -> None:
        """
        Request thread to stop execution and terminate the process.
        
        This method:
        1. Sets the stop event to signal run() method
        2. Immediately stops the SmartCheck.bat process
        
        This ensures immediate termination even if the monitoring
        loop is sleeping.
        
        Usage:
            >>> controller.start()
            >>> time.sleep(10)
            >>> controller.stop()  # Request stop and kill process
            >>> controller.join()  # Wait for thread cleanup
        """
        LogEvt("Stop requested for SmartCheckController")
        self._stop_event.set()
        # Immediately stop the process to avoid waiting for sleep interval
        self.stop_smartcheck_bat()
