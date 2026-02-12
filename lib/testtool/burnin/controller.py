"""
BurnIN Controller

Threading-based controller for managing BurnIN test execution and monitoring.

This module provides the main BurnInController class that:
- Manages BurnIN process lifecycle (install/uninstall/start/stop)
- Configures BurnIN test parameters
- Generates .bits script files
- Monitors UI for test status
- Provides thread-safe execution control
"""

import threading
import time
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.logger import LogEvt, LogErr, LogWarn, LogDebug, logConfig
from .config import BurnInConfig
from .script_generator import BurnInScriptGenerator
from .process_manager import BurnInProcessManager
from .ui_monitor import BurnInUIMonitor
from .exceptions import (
    BurnInError,
    BurnInConfigError,
    BurnInTimeoutError,
    BurnInProcessError,
    BurnInInstallError,
    BurnInUIError,
    BurnInTestFailedError,
)

# Initialize logger configuration
try:
    logConfig()
except Exception:
    # If logger setup fails, fall back to basic logging
    pass


class BurnInController(threading.Thread):
    """
    BurnIN controller for managing BurnIN test execution.
    
    This class inherits from threading.Thread and provides comprehensive
    control over BurnIN test including:
    - Software installation and uninstallation
    - Configuration management and script generation
    - Process control (start/stop/kill)
    - Status monitoring through UI automation
    - Automatic error detection and timeout handling
    
    Attributes:
        installer_path (str): Path to BurnIN installer
        install_path (str): Installation directory for BurnIN
        executable_name (str): Name of BurnIN executable (bit.exe or bit64.exe)
        script_path (str): Path to .bits script file
        config_file_path (str): Path to .bitcfg config file
        license_path (str): Optional path to license file
        test_duration_minutes (int): Test duration in minutes
        test_drive_letter (str): Drive letter to test
        timeout_seconds (int): Maximum execution time in seconds
        timeout_minutes (int): Maximum execution time in minutes
        check_interval_seconds (int): Status check interval in seconds
        enable_screenshot (bool): Enable screenshot capture
        status (bool): Execution status (True=success, False=failure)
        error_count (int): Number of test errors detected
    
    Example:
        >>> controller = BurnInController(
        ...     installer_path="./bin/BurnIn/setup.exe",
        ...     install_path="C:\\\\Program Files\\\\BurnInTest",
        ...     executable_name="bit.exe"
        ... )
        >>> # Install BurnIN
        >>> controller.install()
        >>> 
        >>> # Configure test
        >>> controller.set_config(
        ...     test_duration_minutes=60,
        ...     test_drive_letter="D"
        ... )
        >>> 
        >>> # Run test in thread
        >>> controller.start()
        >>> controller.join(timeout=7200)
        >>> 
        >>> # Check results
        >>> print(f"Status: {controller.status}")
        >>> print(f"Errors: {controller.error_count}")
        >>> 
        >>> # Cleanup
        >>> controller.uninstall()
    """
    
    def __init__(
        self,
        installer_path: str,
        install_path: str = "C:\\Program Files\\BurnInTest",
        executable_name: str = "bit.exe",
        **kwargs
    ):
        """
        Initialize BurnIN controller.
        
        Args:
            installer_path: Path to BurnIN installer executable
            install_path: Installation directory for BurnIN software
            executable_name: Name of BurnIN executable (bit.exe or bit64.exe)
            **kwargs: Additional configuration parameters (optional)
                - license_path: Path to license file
                - script_path: Path to .bits script file
                - config_file_path: Path to .bitcfg config file
                - test_duration_minutes: Test duration in minutes
                - test_drive_letter: Drive letter to test
                - timeout_seconds: Execution timeout in seconds
                - timeout_minutes: Execution timeout in minutes
                - check_interval_seconds: Status check interval
                - ui_retry_max: Maximum UI connection retries
                - ui_retry_interval_seconds: UI retry interval
                - enable_screenshot: Enable screenshot capture
                - etc.
        
        Raises:
            BurnInConfigError: If required paths are invalid
        
        Example:
            >>> controller = BurnInController(
            ...     installer_path="./bin/BurnIn/setup.exe",
            ...     install_path="C:\\\\Program Files\\\\BurnInTest",
            ...     executable_name="bit64.exe",
            ...     test_duration_minutes=120,
            ...     test_drive_letter="E"
            ... )
        """
        super().__init__()
        
        # Validate installer path
        installer = Path(installer_path)
        if not installer.exists():
            LogErr(f"Installer not found at: {installer_path}")
            raise BurnInConfigError(f"Installer not found at: {installer_path}")
        
        # Store basic paths
        self.installer_path = installer_path
        self.install_path = install_path
        self.executable_name = executable_name
        
        # Load default configuration
        default_config = BurnInConfig.get_default_config()
        
        # Installation and execution paths (convert to absolute paths)
        self.license_path: Optional[str] = default_config.get('license_path')
        self.script_path: str = os.path.abspath(default_config['script_path'])
        self.config_file_path: str = os.path.abspath(default_config['config_file_path'])
        
        # Test parameters
        self.test_duration_minutes: int = default_config['test_duration_minutes']
        self.test_drive_letter: str = default_config['test_drive_letter']
        
        # Logging (convert to absolute path)
        self.log_path: str = os.path.abspath(default_config['log_path'])
        self.log_prefix: str = default_config['log_prefix']
        
        # Execution control
        self.timeout_minutes: int = default_config['timeout_minutes']
        self.check_interval_seconds: int = default_config['check_interval_seconds']
        self.ui_retry_max: int = default_config['ui_retry_max']
        self.ui_retry_interval_seconds: float = default_config['ui_retry_interval_seconds']
        
        # Screenshot settings
        self.enable_screenshot: bool = default_config['enable_screenshot']
        self.screenshot_on_error: bool = default_config['screenshot_on_error']
        
        # Test status tracking
        self.status: bool = True  # True = success, False = failure
        self.error_count: int = 0
        self._test_result: Optional[str] = None  # "PASSED", "FAILED", or None
        
        # Internal component managers
        self._process_manager: Optional[BurnInProcessManager] = None
        self._ui_monitor: Optional[BurnInUIMonitor] = None
        self._script_generator: Optional[BurnInScriptGenerator] = None
        
        # Thread control
        self._stop_event = threading.Event()
        self._running = False
        
        # Apply any additional configuration from kwargs
        if kwargs:
            self.set_config(**kwargs)
        
        LogEvt(f"BurnInController initialized with installer={installer_path}, "
               f"install_path={install_path}, executable={executable_name}")
    
    def install(self, license_path: Optional[str] = None) -> bool:
        """
        Install BurnIN software.
        
        Args:
            license_path: Optional path to license file
        
        Returns:
            True if installation successful
        
        Raises:
            BurnInInstallError: If installation fails
        
        Example:
            >>> controller = BurnInController(installer_path="./setup.exe")
            >>> controller.install(license_path="./license.key")
        """
        LogEvt("Starting BurnIN installation...")
        
        try:
            # Create process manager if not exists
            if self._process_manager is None:
                self._process_manager = BurnInProcessManager(
                    install_path=self.install_path,
                    executable_name=self.executable_name
                )
            
            # Use provided license or stored license
            lic_path = license_path or self.license_path
            
            # Perform installation
            success = self._process_manager.install(
                installer_path=self.installer_path,
                license_path=lic_path,
                timeout=300  # 5 minutes for installation
            )
            
            if success:
                LogEvt("BurnIN installation completed successfully")
            else:
                LogErr("BurnIN installation failed")
                raise BurnInInstallError("Installation failed")
            
            return success
            
        except Exception as e:
            LogErr(f"BurnIN installation error: {e}")
            raise BurnInInstallError(f"Installation failed: {e}")
    
    def uninstall(self) -> bool:
        """
        Uninstall BurnIN software.
        
        Returns:
            True if uninstallation successful
        
        Raises:
            BurnInInstallError: If uninstallation fails
        
        Example:
            >>> controller.uninstall()
        """
        LogEvt("Starting BurnIN uninstallation...")
        
        try:
            if self._process_manager is None:
                LogWarn("Process manager not initialized, creating new one")
                self._process_manager = BurnInProcessManager(
                    install_path=self.install_path,
                    executable_name=self.executable_name,
                    installer_path=self.installer_path
                )
            
            # Stop any running process first
            if self.is_running():
                LogWarn("BurnIN process still running, stopping it first")
                self.stop()
            
            # Perform uninstallation
            success = self._process_manager.uninstall(timeout=300)
            
            if success:
                LogEvt("BurnIN uninstallation completed successfully")
            else:
                LogErr("BurnIN uninstallation failed")
            
            return success
            
        except Exception as e:
            LogErr(f"BurnIN uninstallation error: {e}")
            raise BurnInInstallError(f"Uninstallation failed: {e}")
    
    def is_installed(self) -> bool:
        """
        Check if BurnIN is installed.
        
        Returns:
            True if BurnIN is installed
        
        Example:
            >>> if controller.is_installed():
            ...     print("BurnIN is installed")
        """
        if self._process_manager is None:
            self._process_manager = BurnInProcessManager(
                install_path=self.install_path,
                executable_name=self.executable_name
            )
        
        return self._process_manager.is_installed()
    
    def set_config(self, **kwargs) -> None:
        """
        Update configuration parameters.
        
        Args:
            **kwargs: Configuration parameters to update
        
        Raises:
            BurnInConfigError: If validation fails
        
        Example:
            >>> controller.set_config(
            ...     test_duration_minutes=120,
            ...     test_drive_letter="E",
            ...     timeout_minutes=150
            ... )
        """
        LogDebug(f"Updating configuration: {kwargs}")
        
        # Validate configuration
        try:
            BurnInConfig.validate_config(kwargs)
        except ValueError as e:
            raise BurnInConfigError(f"Invalid configuration: {e}")
        
        # Update attributes (convert path parameters to absolute paths)
        path_params = {'script_path', 'config_file_path', 'log_path', 'license_path'}
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                # Convert relative paths to absolute paths
                if key in path_params and value and isinstance(value, str):
                    value = os.path.abspath(value)
                setattr(self, key, value)
                LogDebug(f"Updated {key} = {value}")
            else:
                LogWarn(f"Unknown configuration parameter: {key}")
    
    def _generate_script(self) -> None:
        """
        Generate BurnIN script file (.bits).
        
        Raises:
            BurnInConfigError: If script generation fails
        """
        LogEvt("Generating BurnIN script...")
        
        try:
            if self._script_generator is None:
                self._script_generator = BurnInScriptGenerator()
            
            # Generate script with current configuration
            self._script_generator.generate_disk_test_script(
                config_file_path=self.config_file_path,
                log_path=self.log_path,
                duration_minutes=self.test_duration_minutes,
                drive_letter=self.test_drive_letter,
                output_path=self.script_path
            )
            
            LogEvt(f"Script generated: {self.script_path}")
            
        except Exception as e:
            LogErr(f"Script generation failed: {e}")
            raise BurnInConfigError(f"Script generation failed: {e}")
    
    def _start_process(self) -> None:
        """
        Start BurnIN process with generated script.
        
        Raises:
            BurnInProcessError: If process start fails
        """
        LogEvt("Starting BurnIN process...")
        
        try:
            if self._process_manager is None:
                raise BurnInProcessError("Process manager not initialized")
            
            # Start the process
            pid = self._process_manager.start_process(
                script_path=self.script_path
            )
            
            if pid:
                LogEvt(f"BurnIN process started with PID: {pid}")
            else:
                raise BurnInProcessError("Failed to start BurnIN process")
            
        except Exception as e:
            LogErr(f"Failed to start BurnIN process: {e}")
            raise BurnInProcessError(f"Process start failed: {e}")
    
    def _connect_ui(self) -> None:
        """
        Connect to BurnIN UI window.
        
        Raises:
            BurnInUIError: If UI connection fails
        """
        LogEvt("Connecting to BurnIN UI...")
        
        try:
            if self._ui_monitor is None:
                self._ui_monitor = BurnInUIMonitor(
                    window_title="BurnInTest",
                    retry_max=self.ui_retry_max,
                    retry_interval=self.ui_retry_interval_seconds
                )
            
            # Connect to window
            if self._ui_monitor.connect():
                LogEvt("Connected to BurnIN UI successfully")
            else:
                raise BurnInUIError("Failed to connect to BurnIN UI")
            
        except Exception as e:
            LogErr(f"UI connection failed: {e}")
            raise BurnInUIError(f"UI connection failed: {e}")
    
    def _monitor_loop(self) -> None:
        """
        Main monitoring loop - checks test status periodically.
        
        This runs in the thread and monitors the test progress.
        
        Raises:
            BurnInTimeoutError: If test exceeds timeout
            BurnInTestFailedError: If test fails
        """
        LogEvt("Starting monitoring loop...")
        
        start_time = time.time()
        last_screenshot_time = start_time
        screenshot_interval = 60  # Take screenshot every 60 seconds
        
        try:
            while not self._stop_event.is_set():
                # Check timeout
                elapsed = time.time() - start_time
                timeout_seconds = self.timeout_minutes * 60
                if elapsed > timeout_seconds:
                    LogErr(f"Test timeout after {elapsed:.1f} seconds (timeout: {self.timeout_minutes} minutes)")
                    self._take_screenshot("timeout")
                    raise BurnInTimeoutError(
                        f"Test exceeded timeout of {self.timeout_minutes} minutes ({timeout_seconds} seconds)"
                    )
                
                # Read current status
                try:
                    status = self._ui_monitor.read_status()
                    LogDebug(f"Current status: {status}")
                    
                    # Extract test result from status dict
                    test_result = status.get('test_result', 'unknown')
                    test_running = status.get('test_running', False)
                    
                    # Check if test completed
                    if test_result in ['passed', 'failed']:
                        self._test_result = test_result.upper()
                        LogEvt(f"Test completed with status: {test_result}")
                        
                        # Get error count from status dict
                        self.error_count = status.get('errors', 0)
                        LogEvt(f"Error count: {self.error_count}")
                        
                        # Take final screenshot
                        self._take_screenshot("final")
                        
                        # Set status
                        if test_result == 'passed' and self.error_count == 0:
                            self.status = True
                            LogEvt("Test PASSED successfully")
                        else:
                            self.status = False
                            if test_result == 'failed':
                                LogErr("Test FAILED")
                                raise BurnInTestFailedError(
                                    f"Test failed with {self.error_count} errors"
                                )
                            elif self.error_count > 0:
                                LogWarn(f"Test passed but with {self.error_count} errors")
                        
                        break
                    
                except BurnInUIError as e:
                    LogWarn(f"UI read error: {e}")
                    # Try to reconnect - UI monitor now handles dynamic title changes
                    if not self._ui_monitor.is_connected():
                        LogWarn("UI disconnected, attempting to reconnect...")
                        try:
                            # Give it more time to reconnect (5 retries, 2 seconds each)
                            self._ui_monitor.connect(timeout=10)
                            LogEvt("UI reconnected successfully")
                        except Exception as conn_error:
                            LogErr(f"Reconnection failed: {conn_error}")
                            # Don't fail immediately, continue monitoring
                            # Process might still be running even if UI not accessible
                
                # Handle any popup dialogs (with caution)
                # Note: This is disabled by default to avoid closing main window
                # Only enable if you need to handle error dialogs automatically
                # try:
                #     self._ui_monitor.handle_dialogs()
                # except Exception as e:
                #     LogDebug(f"Dialog handling: {e}")
                
                # Take periodic screenshots
                if self.enable_screenshot:
                    current_time = time.time()
                    if current_time - last_screenshot_time >= screenshot_interval:
                        self._take_screenshot("progress")
                        last_screenshot_time = current_time
                
                # Wait before next check
                time.sleep(self.check_interval_seconds)
            
        except (BurnInTimeoutError, BurnInTestFailedError):
            self.status = False
            raise
        except Exception as e:
            LogErr(f"Monitoring loop error: {e}")
            self.status = False
            raise BurnInError(f"Monitoring failed: {e}")
        finally:
            # Cleanup
            LogEvt("Monitoring loop ended")
            self._running = False
    
    def _take_screenshot(self, prefix: str = "screenshot") -> None:
        """
        Take a screenshot of BurnIN window.
        
        Args:
            prefix: Filename prefix for screenshot
        """
        if not self.enable_screenshot:
            return
        
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"./testlog/{prefix}_{timestamp}.png"
            
            # Create directory if needed
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
            
            self._ui_monitor.take_screenshot(screenshot_path)
            LogEvt(f"Screenshot saved: {screenshot_path}")
            
        except Exception as e:
            LogWarn(f"Failed to take screenshot: {e}")
    
    def run(self) -> None:
        """
        Thread main loop - execute BurnIN test.
        
        This method runs when thread.start() is called.
        It orchestrates the entire test execution:
        1. Generate script
        2. Start process
        3. Connect to UI
        4. Monitor test progress
        5. Handle completion/errors
        
        Example:
            >>> controller = BurnInController(installer_path="./setup.exe")
            >>> controller.install()
            >>> controller.set_config(test_duration_minutes=60)
            >>> controller.start()  # Calls run() in new thread
            >>> controller.join()
            >>> print(controller.status)
        """
        LogEvt("BurnIN controller thread started")
        self._running = True
        
        try:
            # Check if stop requested before starting
            if self._stop_event.is_set():
                LogEvt("Stop requested before execution, exiting...")
                return
            
            # Step 1: Generate script
            LogEvt("Step 1: Generating script...")
            self._generate_script()
            
            # Check if stop requested
            if self._stop_event.is_set():
                LogEvt("Stop requested after script generation, exiting...")
                return
            
            # Step 2: Start BurnIN process
            LogEvt("Step 2: Starting BurnIN process...")
            self._start_process()
            
            # Give process time to start
            time.sleep(3)
            
            # Check if stop requested
            if self._stop_event.is_set():
                LogEvt("Stop requested after process start, exiting...")
                return
            
            # Step 3: Connect to UI
            LogEvt("Step 3: Connecting to UI...")
            self._connect_ui()
            
            # Check if stop requested
            if self._stop_event.is_set():
                LogEvt("Stop requested after UI connection, exiting...")
                return
            
            # Step 4: Monitor test execution
            LogEvt("Step 4: Starting monitoring...")
            self._monitor_loop()
            
            LogEvt("BurnIN test execution completed")
            
        except Exception as e:
            LogErr(f"BurnIN execution error: {e}")
            self.status = False
            
            # Take error screenshot
            if self.screenshot_on_error:
                try:
                    self._take_screenshot("error")
                except Exception as screenshot_error:
                    LogWarn(f"Failed to take screenshot: {screenshot_error}")
            
            # Clean up resources (don't call stop() to avoid recursion)
            try:
                # Disconnect UI if connected
                if self._ui_monitor and self._ui_monitor.is_connected():
                    self._ui_monitor.disconnect()
            except Exception:
                pass
            
            try:
                # Stop process if running
                if self._process_manager and self._process_manager.is_running():
                    self._process_manager.stop_process(timeout=10)
            except Exception:
                try:
                    self._process_manager.kill_process()
                except Exception:
                    pass
        
        finally:
            self._running = False
            LogEvt("BurnIN controller thread ended")
    
    def stop(self, timeout: int = 30) -> None:
        """
        Stop BurnIN execution.
        
        Args:
            timeout: Time to wait for graceful stop before killing (seconds)
        
        Example:
            >>> controller.start()
            >>> time.sleep(10)
            >>> controller.stop()  # Stop execution early
        """
        LogEvt("Stopping BurnIN execution...")
        
        # Signal thread to stop
        self._stop_event.set()
        
        # Disconnect UI
        if self._ui_monitor and self._ui_monitor.is_connected():
            try:
                self._ui_monitor.disconnect()
                LogEvt("UI disconnected")
            except Exception as e:
                LogWarn(f"Error disconnecting UI: {e}")
        
        # Stop process
        if self._process_manager:
            try:
                self._process_manager.stop_process(timeout=timeout)
                LogEvt("BurnIN process stopped")
            except Exception as e:
                LogWarn(f"Error stopping process: {e}")
                # Try to kill if stop failed
                try:
                    self._process_manager.kill_process()
                    LogEvt("BurnIN process killed")
                except Exception as kill_error:
                    LogErr(f"Error killing process: {kill_error}")
    
    def is_running(self) -> bool:
        """
        Check if BurnIN is currently running.
        
        Returns:
            True if BurnIN process is running
        
        Example:
            >>> if controller.is_running():
            ...     print("Test in progress...")
        """
        if self._process_manager is None:
            return False
        
        return self._process_manager.is_running()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current execution status.
        
        Returns:
            Dictionary with status information:
            - running: Whether test is currently running
            - status: Test result (True=success, False=failure)
            - test_result: Test result string ("PASSED"/"FAILED"/None)
            - error_count: Number of errors detected
            - installed: Whether BurnIN is installed
            - process_running: Whether BurnIN process is running
        
        Example:
            >>> status = controller.get_status()
            >>> print(f"Running: {status['running']}")
            >>> print(f"Result: {status['test_result']}")
            >>> print(f"Errors: {status['error_count']}")
        """
        return {
            'running': self._running,
            'status': self.status,
            'test_result': self._test_result,
            'error_count': self.error_count,
            'installed': self.is_installed(),
            'process_running': self.is_running(),
        }
    
    def __repr__(self) -> str:
        """String representation of controller."""
        return (
            f"BurnInController("
            f"installed={self.is_installed()}, "
            f"running={self._running}, "
            f"status={self.status})"
        )
