"""
PythonInstaller Controller

Threading-based controller for managing Python installation and uninstallation.
Supports specifying a target version; verifies the install after completion.
"""

import threading
import sys
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.logger import get_module_logger
from .config import PythonInstallerConfig
from .exceptions import (
    PythonInstallerError,
    PythonInstallerConfigError,
    PythonInstallerTimeoutError,
    PythonInstallerProcessError,
    PythonInstallerInstallError,
    PythonInstallerTestFailedError,
)
from .process_manager import PythonInstallerProcessManager

logger = get_module_logger(__name__)


class PythonInstallerController(threading.Thread):
    """
    Controller for Python installation / uninstallation.

    Runs as a daemon thread.  After ``join()`` completes:
      - ``status`` is ``True``  → operation succeeded
      - ``status`` is ``False`` → operation failed
      - ``status`` is ``None``  → thread has not yet finished

    Example — install Python 3.11::

        controller = PythonInstallerController(version='3.11')
        controller.start()
        controller.join(timeout=300)
        if controller.status:
            print("Python 3.11 installed at:", controller.installed_executable)
        else:
            print("Install failed")

    Example — uninstall::

        controller = PythonInstallerController(
            version='3.11',
            uninstall_after_test=True,
        )
        controller.start()
        controller.join(timeout=300)
    """

    def __init__(self, **kwargs):
        super().__init__(daemon=True)
        self._config: Dict[str, Any] = PythonInstallerConfig.get_default_config()
        if kwargs:
            self._config = PythonInstallerConfig.merge_config(self._config, kwargs)

        # Thread control
        self._stop_event = threading.Event()

        # Result state
        self._status: Optional[bool] = None
        self._error_count: int = 0

        # Populated after successful install
        self._installed_executable: str = ''

        # Build the process manager from current config
        self._process_manager = self._build_process_manager()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_config(self, **kwargs) -> None:
        """Update configuration at runtime (before start())."""
        self._config = PythonInstallerConfig.merge_config(self._config, kwargs)
        self._process_manager = self._build_process_manager()

    def is_installed(self) -> bool:
        """Return True if the target Python version is already installed."""
        return self._process_manager.is_installed()

    def install(self) -> None:
        """
        Perform a synchronous (blocking) install.

        Useful when you do not need thread-based execution.
        Raises PythonInstallerInstallError on failure.
        """
        self._process_manager.install()
        self._installed_executable = self._process_manager.get_executable_path()

    def uninstall(self) -> None:
        """
        Perform a synchronous (blocking) uninstall.

        Raises PythonInstallerInstallError on failure.
        """
        self._process_manager.uninstall()

    @property
    def status(self) -> Optional[bool]:
        """
        Thread execution status.

        Returns:
            None  while thread is running (or not yet started),
            True  on successful completion,
            False on error.
        """
        return self._status

    @property
    def error_count(self) -> int:
        """Number of errors encountered during thread execution."""
        return self._error_count

    @property
    def installed_executable(self) -> str:
        """Path to python.exe after a successful install, or empty string."""
        return self._installed_executable

    def stop(self) -> None:
        """Signal the controller thread to stop at the next check point."""
        logger.info("PythonInstallerController: stop signal received")
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Thread body
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Thread entry point: install (and optionally uninstall) Python."""
        logger.info(
            f"PythonInstallerController: starting "
            f"(version={self._config['version']}, "
            f"arch={self._config['architecture']})"
        )
        try:
            self._execute_operation()
            self._status = True
        except PythonInstallerTestFailedError as exc:
            logger.error(f"PythonInstaller verification failed: {exc}")
            self._error_count += 1
            self._status = False
        except PythonInstallerTimeoutError as exc:
            logger.error(f"PythonInstaller timeout: {exc}")
            self._error_count += 1
            self._status = False
        except PythonInstallerInstallError as exc:
            logger.error(f"PythonInstaller install/uninstall error: {exc}")
            self._error_count += 1
            self._status = False
        except PythonInstallerError as exc:
            logger.error(f"PythonInstaller error: {exc}")
            self._error_count += 1
            self._status = False
        except Exception as exc:
            logger.error(
                f"PythonInstallerController unexpected error: {exc}", exc_info=True
            )
            self._error_count += 1
            self._status = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_operation(self) -> None:
        """Core logic: install, verify, and optionally uninstall Python."""
        if self._stop_event.is_set():
            return

        # --- Install ---
        logger.info(f"Installing Python {self._config['version']} ...")
        self._process_manager.install()
        self._installed_executable = self._process_manager.get_executable_path()

        if not self._installed_executable:
            raise PythonInstallerTestFailedError(
                f"Python {self._config['version']} installation succeeded but "
                "python.exe was not found afterwards"
            )
        logger.info(f"Python installed at: {self._installed_executable}")

        if self._stop_event.is_set():
            return

        # --- Uninstall (optional) ---
        if self._config.get('uninstall_after_test'):
            logger.info(f"Uninstalling Python {self._config['version']} ...")
            self._process_manager.uninstall()
            logger.info("Python uninstalled successfully")

    def _build_process_manager(self) -> PythonInstallerProcessManager:
        """Instantiate a PythonInstallerProcessManager from current config."""
        return PythonInstallerProcessManager(
            version=self._config['version'],
            architecture=self._config['architecture'],
            install_path=self._config['install_path'],
            add_to_path=self._config['add_to_path'],
            installer_path=self._config['installer_path'],
            download_dir=self._config['download_dir'],
            timeout_seconds=self._config['timeout_seconds'],
        )
