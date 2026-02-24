# Module Templates Reference

Copy-paste templates for each module. Replace `<Tool>` with the PascalCase tool name and `<toolname>` with the package name.

---

## `exceptions.py` Template

```python
"""
<Tool> Custom Exceptions

This module defines custom exception classes for <Tool> operations.
All exceptions inherit from <Tool>Error base class.
"""


class <Tool>Error(Exception):
    """Base exception for all <Tool>-related errors."""
    pass


class <Tool>ConfigError(<Tool>Error):
    """
    Configuration error.
    Raised when invalid config params are provided or required params are missing.
    """
    pass


class <Tool>TimeoutError(<Tool>Error):
    """
    Timeout error.
    Raised when <Tool> execution exceeds the configured timeout limit.
    """
    pass


class <Tool>ProcessError(<Tool>Error):
    """
    Process control error.
    Raised when starting, stopping, or monitoring the <Tool> process fails.
    """
    pass


# --- Conditional: only when requires_install: true ---
class <Tool>InstallError(<Tool>Error):
    """
    Installation error.
    Raised when <Tool> installation or uninstallation fails.
    """
    pass
# --- End conditional ---


# --- Conditional: only when has_ui: true ---
class <Tool>UIError(<Tool>Error):
    """
    UI interaction error.
    Raised when pywinauto cannot connect to or interact with the <Tool> window.
    """
    pass
# --- End conditional ---


class <Tool>TestFailedError(<Tool>Error):
    """
    Test failure error.
    Raised when the <Tool> test itself reports a failure result.
    """
    pass
```

---

## `config.py` Template

```python
"""
<Tool> Configuration Management

This module provides configuration management and validation for <Tool>.
"""

import copy
from typing import Dict, Any
from .exceptions import <Tool>ConfigError


class <Tool>Config:
    """
    Configuration manager for <Tool> parameters.

    Example:
        >>> config = <Tool>Config.get_default_config()
        >>> <Tool>Config.validate_config({'executable_path': './bin/tool.exe'})
        True
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        # --- paste config_params here as key: default_value pairs ---
        'executable_path': '',
        'output_dir': './testlog',
        'log_path': './<toolname>.log',
        'timeout_seconds': 300,
        'check_interval_seconds': 2.0,
    }

    VALID_PARAMS: set = set(DEFAULT_CONFIG.keys())

    PARAM_TYPES: Dict[str, type] = {
        'executable_path': str,
        'output_dir': str,
        'log_path': str,
        'timeout_seconds': int,
        'check_interval_seconds': (int, float),
    }

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Return a deep copy of the default configuration."""
        return copy.deepcopy(cls.DEFAULT_CONFIG)

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> bool:
        """
        Validate configuration parameters.

        Args:
            config: Configuration dict to validate.

        Returns:
            True if valid.

        Raises:
            <Tool>ConfigError: If any parameter is invalid.
        """
        for key, value in config.items():
            if key not in cls.VALID_PARAMS:
                raise <Tool>ConfigError(f"Unknown config parameter: '{key}'")
            expected_type = cls.PARAM_TYPES.get(key)
            if expected_type and not isinstance(value, expected_type):
                raise <Tool>ConfigError(
                    f"Parameter '{key}' must be {expected_type}, got {type(value).__name__}"
                )
        return True

    @classmethod
    def merge_config(cls, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge override values into base config.

        Args:
            base: Base configuration dict.
            overrides: Values to override.

        Returns:
            Merged configuration dict.
        """
        cls.validate_config(overrides)
        merged = copy.deepcopy(base)
        merged.update(overrides)
        return merged
```

---

## `controller.py` Template

```python
"""
<Tool> Controller

Threading-based controller for managing <Tool> execution and monitoring.
"""

import threading
import time
import sys
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.logger import get_module_logger
from .config import <Tool>Config
from .exceptions import (
    <Tool>Error,
    <Tool>ConfigError,
    <Tool>TimeoutError,
    <Tool>ProcessError,
    <Tool>TestFailedError,
)

# --- Conditional imports ---
# from .process_manager import <Tool>ProcessManager   # if requires_install
# from .script_generator import <Tool>ScriptGenerator # if has_script_generator
# from .ui_monitor import <Tool>UIMonitor             # if has_ui
# --- End conditional ---

logger = get_module_logger(__name__)


class <Tool>Controller(threading.Thread):
    """
    <Tool> controller for managing test execution.

    Example:
        >>> controller = <Tool>Controller(executable_path='./bin/tool.exe')
        >>> controller.set_config(timeout_seconds=120)
        >>> controller.start()
        >>> controller.join(timeout=120)
        >>> assert controller.status is True
    """

    def __init__(self, **kwargs):
        super().__init__(daemon=True)
        # Load defaults and apply any constructor kwargs
        self._config: Dict[str, Any] = <Tool>Config.get_default_config()
        if kwargs:
            self._config = <Tool>Config.merge_config(self._config, kwargs)

        # Thread control
        self._stop_event = threading.Event()

        # Result state
        self._status: Optional[bool] = None
        self._error_count: int = 0

        # Sub-components (conditionally instantiated)
        # self._process_manager = <Tool>ProcessManager(...)  # if requires_install
        # self._ui_monitor = <Tool>UIMonitor(...)            # if has_ui

    def set_config(self, **kwargs) -> None:
        """Update configuration at runtime."""
        self._config = <Tool>Config.merge_config(self._config, kwargs)

    # --- Conditional: only when requires_install: true ---
    def is_installed(self) -> bool:
        """Check if <Tool> is installed."""
        return self._process_manager.is_installed()

    def install(self) -> None:
        """Install <Tool>."""
        self._process_manager.install(
            installer_path=self._config['installer_path']
        )
    # --- End conditional ---

    @property
    def status(self) -> Optional[bool]:
        """
        Execution status.
        Returns None while running, True on pass, False on fail.
        """
        return self._status

    @property
    def error_count(self) -> int:
        """Number of errors detected during test execution."""
        return self._error_count

    def stop(self) -> None:
        """Signal the controller to stop execution."""
        logger.info("<Tool>Controller: stop signal received")
        self._stop_event.set()

    def run(self) -> None:
        """Thread body: execute test and set status."""
        logger.info("<Tool>Controller: starting test execution")
        try:
            self._execute_test()
        except <Tool>TestFailedError as e:
            logger.error(f"<Tool> test failed: {e}")
            self._status = False
        except <Tool>TimeoutError as e:
            logger.error(f"<Tool> timeout: {e}")
            self._status = False
        except <Tool>Error as e:
            logger.error(f"<Tool> error: {e}")
            self._status = False
        except Exception as e:
            logger.error(f"<Tool>Controller unexpected error: {e}", exc_info=True)
            self._status = False

    def _execute_test(self) -> None:
        """
        Core test execution logic.
        Override or extend this method per tool requirements.
        """
        timeout = self._config['timeout_seconds']
        interval = self._config['check_interval_seconds']
        elapsed = 0.0

        # TODO: Start process / initiate tool execution

        while not self._stop_event.is_set() and elapsed < timeout:
            # TODO: Poll for completion / read status
            # Example: check log file, read stdout, query UI, read RunCard
            if self._check_completion():
                return
            time.sleep(interval)
            elapsed += interval

        if elapsed >= timeout:
            raise <Tool>TimeoutError(
                f"<Tool> execution timeout after {timeout} seconds"
            )

    def _check_completion(self) -> bool:
        """
        Check if the test has completed.
        Returns True if done (sets self._status accordingly), False if still running.
        """
        # TODO: Implement result_parsing logic based on spec method
        # log_file: open log, search for pass_pattern / fail_pattern
        # stdout: captured from subprocess
        # runcard: open RunCard.ini, read [Result] section
        # ui: self._ui_monitor.read_status()
        return False
```

---

## `__init__.py` Template

```python
"""
<Tool> Package

<One-line description from spec>

Main Components:
- <Tool>Controller: Main controller class (threading.Thread)
- <Tool>Config: Configuration management and validation
- Custom exceptions for error handling

Usage:
    from lib.testtool.<package_name> import <Tool>Controller

    controller = <Tool>Controller(
        executable_path="./bin/<executable>",
    )
    controller.set_config(timeout_seconds=120)
    controller.start()
    controller.join(timeout=120)

    if controller.status:
        print("<Tool> PASSED")
    else:
        print("<Tool> FAILED")
"""

from .controller import <Tool>Controller
from .config import <Tool>Config
from .exceptions import (
    <Tool>Error,
    <Tool>ConfigError,
    <Tool>TimeoutError,
    <Tool>ProcessError,
    <Tool>TestFailedError,
    # <Tool>InstallError,  # uncomment if requires_install
    # <Tool>UIError,       # uncomment if has_ui
)

__version__ = '1.0.0'

__all__ = [
    '<Tool>Controller',
    '<Tool>Config',
    '<Tool>Error',
    '<Tool>ConfigError',
    '<Tool>TimeoutError',
    '<Tool>ProcessError',
    '<Tool>TestFailedError',
    # '<Tool>InstallError',
    # '<Tool>UIError',
]
```

---

## `process_manager.py` Template *(only if `requires_install: true`)*

```python
"""
<Tool> Process Manager

Process lifecycle management for <Tool>: install, start, stop, kill.
"""

import os
import subprocess
import time
import psutil
from typing import Optional
from pathlib import Path

from .exceptions import <Tool>ProcessError, <Tool>InstallError, <Tool>TimeoutError
from lib.logger import get_module_logger

logger = get_module_logger(__name__)


class <Tool>ProcessManager:
    """Manages install/uninstall and process lifecycle for <Tool>."""

    def __init__(self, install_path: str, executable_name: str = "<executable>"):
        self.install_path = Path(install_path)
        self.executable_name = executable_name
        self._pid: Optional[int] = None
        self._process: Optional[subprocess.Popen] = None

    def is_installed(self) -> bool:
        """Check if <Tool> is installed at install_path."""
        return (self.install_path / self.executable_name).exists()

    def install(self, installer_path: str, **kwargs) -> None:
        """Run silent installation."""
        if not os.path.exists(installer_path):
            raise <Tool>InstallError(f"Installer not found: {installer_path}")
        result = subprocess.run([installer_path, '/S'], capture_output=True, timeout=300)
        if result.returncode != 0:
            raise <Tool>InstallError(f"Installation failed: {result.stderr.decode()}")
        logger.info("<Tool> installed successfully")

    def uninstall(self) -> None:
        """Run silent uninstallation."""
        uninstaller = self.install_path / 'uninstall.exe'
        if uninstaller.exists():
            subprocess.run([str(uninstaller), '/S'], timeout=120)

    def start_process(self, *args) -> subprocess.Popen:
        """Start <Tool> process. Returns the Popen handle."""
        exe = str(self.install_path / self.executable_name)
        self._process = subprocess.Popen([exe, *args])
        self._pid = self._process.pid
        logger.info(f"<Tool> started with PID {self._pid}")
        return self._process

    def stop_process(self) -> None:
        """Gracefully terminate the process."""
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=30)
            self._pid = None

    def kill_process(self) -> None:
        """Force-kill via psutil."""
        if self._pid:
            try:
                proc = psutil.Process(self._pid)
                proc.kill()
            except psutil.NoSuchProcess:
                pass
            self._pid = None

    def is_running(self) -> bool:
        """Check if the process is still alive."""
        if self._pid is None:
            return False
        return psutil.pid_exists(self._pid)
```

---

## `ui_monitor.py` Template *(only if `has_ui: true`)*

```python
"""
<Tool> UI Monitor

Window monitoring and interaction using pywinauto.
"""

import time
import os
from typing import Optional
from pathlib import Path

try:
    from pywinauto import Application
    from pywinauto.findwindows import ElementNotFoundError
    from pywinauto.timings import TimeoutError as PywinautoTimeoutError
except ImportError:
    Application = None
    ElementNotFoundError = Exception
    PywinautoTimeoutError = Exception

from .exceptions import <Tool>UIError, <Tool>TimeoutError
from lib.logger import get_module_logger

logger = get_module_logger(__name__)


class <Tool>UIMonitor:
    """
    UI monitor for <Tool>.
    Connects to the application window and reads status.
    """

    def __init__(
        self,
        window_title: str = "<Default Window Title>",
        retry_max: int = 60,
        retry_interval: float = 1.0
    ):
        self.window_title = window_title
        self.retry_max = retry_max
        self.retry_interval = retry_interval
        self._app = None
        self._window = None

    def connect(self) -> bool:
        """Connect to the application window. Returns True on success."""
        if Application is None:
            raise <Tool>UIError("pywinauto is not installed")
        for attempt in range(self.retry_max):
            try:
                self._app = Application(backend="uia").connect(
                    title_re=self.window_title, timeout=5
                )
                self._window = self._app.window(title_re=self.window_title)
                self._window.wait('ready', timeout=10)
                logger.info(f"<Tool> UI connected after {attempt + 1} attempts")
                return True
            except (ElementNotFoundError, PywinautoTimeoutError):
                time.sleep(self.retry_interval)
        raise <Tool>UIError(f"Could not connect to '{self.window_title}' after {self.retry_max} retries")

    def read_status(self) -> str:
        """Read the status text from the window. Returns status string."""
        if not self._window:
            raise <Tool>UIError("Not connected. Call connect() first.")
        # TODO: Adapt control identifier to actual window structure
        status_el = self._window.child_window(auto_id="statusText")
        return status_el.window_text()

    def get_error_count(self) -> int:
        """Read error count from the window."""
        # TODO: Adapt to actual window control
        return 0

    def capture_screenshot(self, path: str) -> str:
        """Capture screenshot to path. Returns the file path."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if self._window:
            self._window.capture_as_image().save(path)
            logger.info(f"Screenshot saved: {path}")
        return path

    def disconnect(self) -> None:
        """Release window references."""
        self._window = None
        self._app = None
```

---

## `script_generator.py` Template *(only if `has_script_generator: true`)*

```python
"""
<Tool> Script Generator

Generates configuration/script files required by <Tool>.
"""

import os
from typing import Optional
from pathlib import Path


class <Tool>ScriptGenerator:
    """
    Script generator for <Tool>.
    All methods are static — no instantiation needed.

    Example:
        >>> path = <Tool>ScriptGenerator.generate_script(
        ...     output_path="./test.cfg",
        ...     duration=60
        ... )
    """

    @staticmethod
    def generate_script(output_path: str, **kwargs) -> str:
        """
        Generate a configuration/script file for <Tool>.

        Args:
            output_path: Path to save the generated file.
            **kwargs: Tool-specific parameters.

        Returns:
            str: Path to the generated file.

        Raises:
            ValueError: If parameters are invalid.
            OSError: If file cannot be written.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # TODO: Build file content based on kwargs
        content = ""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path
```
