"""
BurnIN UI Monitor

This module provides UI monitoring and interaction for BurnIN test tool.
Uses pywinauto for window automation.
"""

import time
import os
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

try:
    from pywinauto import Application
    from pywinauto.findwindows import ElementNotFoundError
    from pywinauto.timings import TimeoutError as PywinautoTimeoutError
except ImportError:
    # Allow import even if pywinauto not installed (for testing)
    Application = None
    ElementNotFoundError = Exception
    PywinautoTimeoutError = Exception

from .exceptions import BurnInUIError, BurnInTimeoutError


class BurnInUIMonitor:
    """
    UI monitor for BurnIN test tool.
    
    This class handles:
    - Window connection and monitoring
    - Status reading from UI
    - Dialog handling
    - Screenshot capture
    
    Example:
        >>> monitor = BurnInUIMonitor(
        ...     window_title="PassMark BurnInTest",
        ...     timeout=60
        ... )
        >>> 
        >>> # Connect to window
        >>> if monitor.connect():
        ...     # Read status
        ...     status = monitor.read_status()
        ...     print(f"Status: {status}")
        ...     
        ...     # Check for errors
        ...     errors = monitor.get_error_count()
        ...     print(f"Errors: {errors}")
    """
    
    def __init__(
        self,
        window_title: str = "PassMark BurnInTest",
        retry_max: int = 60,
        retry_interval: float = 1.0
    ):
        """
        Initialize UI monitor.
        
        Args:
            window_title: Title of BurnIN window to monitor
            retry_max: Maximum connection retry attempts
            retry_interval: Interval between retries in seconds
        
        Example:
            >>> monitor = BurnInUIMonitor(
            ...     window_title="PassMark BurnInTest",
            ...     retry_max=30,
            ...     retry_interval=2.0
            ... )
        """
        if Application is None:
            raise ImportError("pywinauto is required for UI monitoring")
        
        self.window_title = window_title
        self.retry_max = retry_max
        self.retry_interval = retry_interval
        
        # Window objects
        self._app: Optional[Application] = None
        self._window = None
        self._connected = False
    
    def connect(self, timeout: Optional[int] = None) -> bool:
        """
        Connect to BurnIN window.
        
        Args:
            timeout: Connection timeout in seconds (uses retry_max if None)
        
        Returns:
            bool: True if connection successful
        
        Raises:
            BurnInUIError: If connection fails after retries
            BurnInTimeoutError: If connection times out
        
        Example:
            >>> monitor = BurnInUIMonitor()
            >>> if monitor.connect(timeout=30):
            ...     print("Connected to BurnIN window")
        """
        if timeout is None:
            max_retries = self.retry_max
        else:
            max_retries = int(timeout / self.retry_interval)
        
        for attempt in range(max_retries):
            try:
                # Try to connect to window
                self._app = Application(backend="uia").connect(
                    title_re=f".*{self.window_title}.*",
                    timeout=self.retry_interval
                )
                
                # Get main window
                self._window = self._app.window(title_re=f".*{self.window_title}.*")
                
                # Verify window is accessible
                if self._window.exists():
                    self._connected = True
                    return True
                    
            except ElementNotFoundError:
                # Window not found, retry
                time.sleep(self.retry_interval)
                continue
            except PywinautoTimeoutError:
                # Timeout, retry
                time.sleep(self.retry_interval)
                continue
            except Exception as e:
                # Other error
                if attempt == max_retries - 1:
                    raise BurnInUIError(f"Failed to connect to window: {e}")
                time.sleep(self.retry_interval)
                continue
        
        raise BurnInTimeoutError(
            f"Failed to connect to BurnIN window after {max_retries} attempts"
        )
    
    def is_connected(self) -> bool:
        """
        Check if connected to window.
        
        Returns:
            bool: True if connected
        
        Example:
            >>> if monitor.is_connected():
            ...     print("Still connected")
        """
        if not self._connected or self._window is None:
            return False
        
        try:
            # Try to check if window still exists
            # Note: Window title may change during test execution
            # (e.g., "BurnInTest" -> "BurnInTest - 50% Complete")
            # So we need to be more flexible
            if self._window.exists():
                return True
            
            # If original window not found, try to reconnect with flexible title
            # This handles cases where window title changes during test
            from pywinauto import Desktop
            windows = Desktop(backend="uia").windows()
            for window in windows:
                try:
                    title = window.window_text()
                    if self.window_title.lower() in title.lower():
                        # Found window with matching title
                        self._window = window
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception:
            return False
    
    def disconnect(self) -> None:
        """
        Disconnect from window.
        
        Example:
            >>> monitor.disconnect()
        """
        self._window = None
        self._app = None
        self._connected = False
    
    def read_status(self) -> Dict[str, Any]:
        """
        Read current test status from UI.
        
        Returns:
            Dict[str, Any]: Status information including:
                - test_running: bool
                - elapsed_time: str
                - errors: int
                - test_result: str ('running', 'passed', 'failed', 'unknown')
        
        Raises:
            BurnInUIError: If not connected or cannot read status
        
        Example:
            >>> status = monitor.read_status()
            >>> print(f"Test running: {status['test_running']}")
            >>> print(f"Errors: {status['errors']}")
        """
        if not self.is_connected():
            raise BurnInUIError("Not connected to BurnIN window")
        
        try:
            status = {
                'test_running': False,
                'elapsed_time': '00:00:00',
                'errors': 0,
                'test_result': 'unknown'
            }
            
            # Read status from BurnIN status image control (auto_id="14004")
            # This is the actual status display element in BurnIN window
            try:
                statusImage = self._window.child_window(auto_id="14004", control_type="Image")
                
                if statusImage.exists(timeout=2):
                    # Get status text from the image control
                    # Examples: "Running (0 Errors)", "Tests Passed", "Tests Failed"
                    test_status_text = statusImage.texts()[0] if statusImage.texts() else ""
                    test_status_upper = test_status_text.upper().replace(" ", "")
                    
                    # Parse test status
                    if "RUNNING" in test_status_upper or "STARTING" in test_status_upper:
                        status['test_running'] = True
                        status['test_result'] = 'running'
                        
                        # Extract error count using regex: (5 ERRORS)
                        import re
                        error_match = re.search(r'\((\d+)ERRORS?\)', test_status_upper)
                        if error_match:
                            status['errors'] = int(error_match.group(1))
                    
                    elif "TESTSPASSED" in test_status_upper or "PASSED" in test_status_upper:
                        status['test_running'] = False
                        status['test_result'] = 'passed'
                        
                        # Also check for error count in passed status
                        import re
                        error_match = re.search(r'\((\d+)ERRORS?\)', test_status_upper)
                        if error_match:
                            status['errors'] = int(error_match.group(1))
                    
                    elif "FAILED" in test_status_upper or "TESTSFAILED" in test_status_upper:
                        status['test_running'] = False
                        status['test_result'] = 'failed'
                        
                        # Extract error count
                        import re
                        error_match = re.search(r'\((\d+)ERRORS?\)', test_status_upper)
                        if error_match:
                            status['errors'] = int(error_match.group(1))
                    
                    else:
                        # Unknown status
                        status['test_result'] = 'unknown'
                    
                else:
                    # Status image not found, try fallback method
                    window_text = self._window.window_text()
                    if 'Running' in window_text:
                        status['test_running'] = True
                        status['test_result'] = 'running'
                    
            except Exception as e:
                # Fallback: try to get info from window title
                try:
                    window_text = self._window.window_text()
                    if 'Running' in window_text or 'Testing' in window_text:
                        status['test_running'] = True
                        status['test_result'] = 'running'
                except Exception:
                    pass
            
            return status
            
        except Exception as e:
            raise BurnInUIError(f"Failed to read status: {e}")
    
    def get_error_count(self) -> int:
        """
        Get current error count.
        
        Returns:
            int: Number of errors detected
        
        Raises:
            BurnInUIError: If cannot read error count
        
        Example:
            >>> errors = monitor.get_error_count()
            >>> if errors > 0:
            ...     print(f"Test has {errors} errors")
        """
        status = self.read_status()
        return status.get('errors', 0)
    
    def is_test_running(self) -> bool:
        """
        Check if test is currently running.
        
        Returns:
            bool: True if test is running
        
        Raises:
            BurnInUIError: If cannot determine test status
        
        Example:
            >>> if monitor.is_test_running():
            ...     print("Test is still running")
        """
        status = self.read_status()
        return status.get('test_running', False)
    
    def wait_for_completion(
        self,
        timeout: int = 3600,
        check_interval: float = 2.0
    ) -> str:
        """
        Wait for test to complete.
        
        Args:
            timeout: Maximum wait time in seconds
            check_interval: Check interval in seconds
        
        Returns:
            str: Test result ('passed', 'failed', 'timeout')
        
        Raises:
            BurnInUIError: If error occurs during wait
        
        Example:
            >>> result = monitor.wait_for_completion(timeout=7200)
            >>> print(f"Test result: {result}")
        """
        if not self.is_connected():
            raise BurnInUIError("Not connected to BurnIN window")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                status = self.read_status()
                
                # Check if test completed
                if not status['test_running']:
                    return status['test_result']
                
                # Check for dialogs
                self.handle_dialogs()
                
                time.sleep(check_interval)
                
            except Exception as e:
                # Log error but continue waiting
                time.sleep(check_interval)
                continue
        
        return 'timeout'
    
    def handle_dialogs(self) -> bool:
        """
        Handle any popup dialogs.
        
        Returns:
            bool: True if dialog was handled
        
        Example:
            >>> if monitor.handle_dialogs():
            ...     print("Handled a dialog")
        """
        if not self.is_connected():
            return False
        
        try:
            # Look for common dialog windows (excluding main window)
            # Only look for actual dialog boxes like error messages
            dialog_titles = [
                'Error',
                'Warning',
                'Information',
                'BurnInTest Error',  # Specific error dialogs only
            ]
            
            for title in dialog_titles:
                try:
                    # Find dialogs - but exclude the main window
                    dialogs = self._app.windows(title_re=f".*{title}.*")
                    
                    for dialog in dialogs:
                        # Skip if this is the main window
                        if dialog == self._window:
                            continue
                        
                        # Check if this is actually a dialog (has OK/Close/Cancel buttons)
                        if not dialog.exists(timeout=0.5):
                            continue
                        
                        is_dialog = False
                        
                        # Try to close dialog by clicking OK/Close/Cancel button
                        try:
                            if dialog.OK.exists(timeout=0.5):
                                dialog.OK.click()
                                is_dialog = True
                        except:
                            pass
                        
                        if not is_dialog:
                            try:
                                if dialog.Close.exists(timeout=0.5):
                                    dialog.Close.click()
                                    is_dialog = True
                            except:
                                pass
                        
                        if not is_dialog:
                            try:
                                if dialog.Cancel.exists(timeout=0.5):
                                    dialog.Cancel.click()
                                    is_dialog = True
                            except:
                                pass
                        
                        if is_dialog:
                            return True
                        
                except:
                    continue
            
            return False
            
        except Exception:
            return False
    
    def take_screenshot(
        self,
        output_path: str,
        window_only: bool = True
    ) -> str:
        """
        Take screenshot of BurnIN window.
        
        Args:
            output_path: Path to save screenshot
            window_only: If True, capture window only; if False, capture full screen
        
        Returns:
            str: Path to saved screenshot
        
        Raises:
            BurnInUIError: If screenshot fails
        
        Example:
            >>> path = monitor.take_screenshot("./screenshot.png")
            >>> print(f"Screenshot saved: {path}")
        """
        if not self.is_connected():
            raise BurnInUIError("Not connected to BurnIN window")
        
        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Take screenshot
            if window_only:
                self._window.capture_as_image().save(output_path)
            else:
                # Full screen screenshot
                import pyautogui
                screenshot = pyautogui.screenshot()
                screenshot.save(output_path)
            
            return output_path
            
        except Exception as e:
            raise BurnInUIError(f"Failed to take screenshot: {e}")
    
    def click_button(self, button_name: str, timeout: float = 5.0) -> bool:
        """
        Click a button in the window.
        
        Args:
            button_name: Name or text of button to click
            timeout: Timeout for finding button
        
        Returns:
            bool: True if button was clicked
        
        Raises:
            BurnInUIError: If button not found or click fails
        
        Example:
            >>> monitor.click_button("Start")
            >>> monitor.click_button("Stop")
        """
        if not self.is_connected():
            raise BurnInUIError("Not connected to BurnIN window")
        
        try:
            # Try to find button by name
            button = self._window.child_window(
                title=button_name,
                control_type="Button",
                timeout=timeout
            )
            
            if button.exists():
                button.click()
                return True
            else:
                raise BurnInUIError(f"Button '{button_name}' not found")
                
        except Exception as e:
            raise BurnInUIError(f"Failed to click button '{button_name}': {e}")
    
    def get_window_info(self) -> Dict[str, Any]:
        """
        Get information about the window.
        
        Returns:
            Dict[str, Any]: Window information including:
                - title: str
                - visible: bool
                - enabled: bool
                - rect: tuple (left, top, right, bottom)
        
        Raises:
            BurnInUIError: If not connected
        
        Example:
            >>> info = monitor.get_window_info()
            >>> print(f"Window: {info['title']}")
            >>> print(f"Visible: {info['visible']}")
        """
        if not self.is_connected():
            raise BurnInUIError("Not connected to BurnIN window")
        
        try:
            return {
                'title': self._window.window_text(),
                'visible': self._window.is_visible(),
                'enabled': self._window.is_enabled(),
                'rect': self._window.rectangle(),
            }
        except Exception as e:
            raise BurnInUIError(f"Failed to get window info: {e}")
    
    def wait_for_window(
        self,
        timeout: int = 60,
        check_interval: float = 1.0
    ) -> bool:
        """
        Wait for BurnIN window to appear.
        
        Args:
            timeout: Maximum wait time in seconds
            check_interval: Check interval in seconds
        
        Returns:
            bool: True if window appeared
        
        Raises:
            BurnInTimeoutError: If window doesn't appear within timeout
        
        Example:
            >>> if monitor.wait_for_window(timeout=30):
            ...     print("Window appeared")
            ...     monitor.connect()
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                if self.connect(timeout=int(check_interval)):
                    return True
            except:
                time.sleep(check_interval)
                continue
        
        raise BurnInTimeoutError(
            f"BurnIN window did not appear within {timeout} seconds"
        )
    
    def read_text_field(self, field_name: str, timeout: float = 5.0) -> str:
        """
        Read text from a text field or label.
        
        Args:
            field_name: Name or automation ID of the field
            timeout: Timeout for finding field
        
        Returns:
            str: Text content
        
        Raises:
            BurnInUIError: If field not found or cannot read
        
        Example:
            >>> elapsed = monitor.read_text_field("ElapsedTime")
            >>> print(f"Elapsed: {elapsed}")
        """
        if not self.is_connected():
            raise BurnInUIError("Not connected to BurnIN window")
        
        try:
            # Try to find field by automation ID or name
            field = self._window.child_window(
                auto_id=field_name,
                timeout=timeout
            )
            
            if not field.exists():
                # Try by title
                field = self._window.child_window(
                    title=field_name,
                    timeout=timeout
                )
            
            if field.exists():
                return field.window_text()
            else:
                raise BurnInUIError(f"Field '{field_name}' not found")
                
        except Exception as e:
            raise BurnInUIError(f"Failed to read field '{field_name}': {e}")
