"""
Diskercise Controller

Threading-based controller for managing Diskercise GUI test execution.

Supports:
- Single-window mode: run() launches one instance and monitors it.
- Multi-instance mode: open_instance() + start_all_instances() to run
  several Diskercise.exe processes concurrently (e.g. STC-401 pattern).
"""

import threading
import time
import sys
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.logger import get_module_logger
from .config import DiskerciseConfig
from .exceptions import (
    DiskerciseError,
    DiskerciseConfigError,
    DiskerciseTimeoutError,
    DiskerciseProcessError,
    DiskerciseUIError,
    DiskerciseTestFailedError,
)
from .ui_monitor import DiskerciseUIMonitor, DiskerciseInstance

logger = get_module_logger(__name__)


class DiskerciseController(threading.Thread):
    """
    Diskercise controller — single or multi-instance.

    Single-instance example:
        >>> ctrl = DiskerciseController(
        ...     exe_path=r'C:\\tools\\Diskercise\\Diskercise.exe'
        ... )
        >>> ctrl.set_config(thread_count=4, file_size_mb=100, test_duration_minutes=30)
        >>> ctrl.start()
        >>> ctrl.join()
        >>> assert ctrl.status is True  # True=pass, False=fail

    Multi-instance example (STC-401 pattern):
        >>> ctrl = DiskerciseController(
        ...     exe_path=r'C:\\tools\\Diskercise\\Diskercise.exe'
        ... )
        >>> ctrl.open_instance(dest_folder=r'C:\\1', config={'thread_count': 2})
        >>> ctrl.open_instance(dest_folder=r'C:\\2', config={'thread_count': 2})
        >>> ctrl.start_all_instances()     # click Start on all windows
        >>> ctrl.start()                   # begin scan thread
        >>> ctrl.join()
        >>> assert ctrl.status is True
    """

    def __init__(self, exe_path: str = '', **kwargs):
        """
        Initialize the Diskercise controller.

        Args:
            exe_path: Path to Diskercise.exe. Falls back to DISKERCISE_PATH env var.
            **kwargs: Any DiskerciseConfig parameter overrides.

        Raises:
            DiskerciseConfigError: If exe_path cannot be resolved.
        """
        super().__init__(daemon=True)

        # Resolve exe_path
        resolved = exe_path or os.path.join(
            os.environ.get('DISKERCISE_PATH', ''), 'Diskercise.exe'
        )

        self._config: Dict[str, Any] = DiskerciseConfig.get_default_config()
        self._config['exe_path'] = resolved

        if kwargs:
            self._config = DiskerciseConfig.merge_config(self._config, kwargs)

        # Thread control
        self._stop_event = threading.Event()

        # Result state
        self._status: Optional[bool] = None
        self._error_count: int = 0
        self._failure_message: str = ''

        # UI monitor
        self._monitor = DiskerciseUIMonitor(
            window_wait_timeout=self._config['window_wait_timeout'],
            ui_retry_max=self._config['ui_retry_max'],
        )

        # Instances managed in multi-instance mode
        self._instances: List[DiskerciseInstance] = []
        self._instances_lock = threading.Lock()

        # Single-instance handle (used when run() launches its own instance)
        self._single_instance: Optional[DiskerciseInstance] = None

    # ------------------------------------------------------------------ #
    #  Public configuration API
    # ------------------------------------------------------------------ #

    def set_config(self, **kwargs) -> None:
        """Update configuration at runtime (before start())."""
        self._config = DiskerciseConfig.merge_config(self._config, kwargs)
        self._monitor.window_wait_timeout = self._config['window_wait_timeout']
        self._monitor.ui_retry_max = self._config['ui_retry_max']

    # ------------------------------------------------------------------ #
    #  Status properties
    # ------------------------------------------------------------------ #

    @property
    def status(self) -> Optional[bool]:
        """
        Execution result.
        None while running, True on pass, False on fail.
        """
        return self._status

    @property
    def error_count(self) -> int:
        """Number of errors detected during execution."""
        return self._error_count

    @property
    def failure_message(self) -> str:
        """Description of the first failure encountered."""
        return self._failure_message

    # ------------------------------------------------------------------ #
    #  Stop signal
    # ------------------------------------------------------------------ #

    def stop(self) -> None:
        """Signal the controller to stop scanning and exit."""
        logger.info("DiskerciseController: stop signal received")
        self._stop_event.set()

    # ------------------------------------------------------------------ #
    #  Multi-instance API
    # ------------------------------------------------------------------ #

    def open_instance(
        self,
        dest_folder: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Copy Diskercise.exe to dest_folder, launch it, and register the instance.

        The instance is launched but NOT started (Start button not clicked yet).
        Call start_all_instances() after all instances are opened.

        Args:
            dest_folder: Directory to copy the exe into. Created if it doesn't exist.
            config: Per-instance config overrides (merged on top of self._config).

        Returns:
            Index of the new instance in the internal list.

        Raises:
            DiskerciseProcessError: If the exe copy or launch fails.
            DiskerciseUIError: If the window cannot be connected.
        """
        base_exe = self._config['exe_path']
        try:
            dest_exe = DiskerciseUIMonitor.copy_exe_to_folder(base_exe, dest_folder)
        except Exception as e:
            raise DiskerciseProcessError(f"Failed to copy Diskercise.exe to {dest_folder}: {e}")

        # Build per-instance config
        inst_config = DiskerciseConfig.merge_config(self._config, config or {})
        inst_config['exe_path'] = dest_exe

        instance = self._monitor.launch(dest_exe)

        # Apply GUI config
        self._monitor.set_gui_config(instance, inst_config)

        with self._instances_lock:
            self._instances.append(instance)
            idx = len(self._instances) - 1

        logger.info(f"DiskerciseController: opened instance #{idx} at {dest_folder}")
        return idx

    def start_all_instances(self) -> None:
        """
        Click the Start button on every registered instance.

        Call this after all open_instance() calls are done, before start().
        """
        with self._instances_lock:
            instances = list(self._instances)
        for i, inst in enumerate(instances):
            logger.info(f"DiskerciseController: starting instance #{i}")
            self._monitor.click_start(inst)

    def stop_all_instances(self) -> None:
        """Click Stop on all instances and close them."""
        with self._instances_lock:
            instances = list(self._instances)
        for inst in instances:
            try:
                self._monitor.click_stop(inst)
            except Exception:
                pass
        self._monitor.close_all(instances)
        with self._instances_lock:
            self._instances.clear()

    # ------------------------------------------------------------------ #
    #  Thread body
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Thread body: launch (if single mode) then scan until done or stopped."""
        logger.info("DiskerciseController: thread started")
        try:
            self._execute_test()
            self._status = True
            logger.info("DiskerciseController: test PASSED")
        except DiskerciseTestFailedError as e:
            logger.error(f"DiskerciseController: test FAILED — {e}")
            self._failure_message = str(e)
            self._error_count += 1
            self._status = False
        except DiskerciseTimeoutError as e:
            logger.error(f"DiskerciseController: timeout — {e}")
            self._failure_message = str(e)
            self._status = False
        except DiskerciseError as e:
            logger.error(f"DiskerciseController: error — {e}")
            self._failure_message = str(e)
            self._status = False
        except Exception as e:
            logger.error(f"DiskerciseController: unexpected error — {e}", exc_info=True)
            self._failure_message = str(e)
            self._status = False

    def _execute_test(self) -> None:
        """
        Core test logic.

        If multi-instance mode (instances already registered and started via the
        public API), this method only runs the scan loop.

        If single-instance mode (no pre-registered instances), this method
        launches one instance, configures it, clicks Start, then scans.
        """
        single_mode = False
        with self._instances_lock:
            if not self._instances:
                single_mode = True

        if single_mode:
            self._run_single_instance()
        else:
            self._scan_instances()

    def _run_single_instance(self) -> None:
        """Launch, configure, start, and scan a single Diskercise instance."""
        exe_path = self._config['exe_path']
        logger.info(f"DiskerciseController: launching single instance from {exe_path}")

        instance = self._monitor.launch(exe_path)
        self._single_instance = instance
        with self._instances_lock:
            self._instances.append(instance)

        self._monitor.set_gui_config(instance, self._config)
        self._monitor.click_start(instance)

        try:
            self._scan_instances()
        finally:
            try:
                self._monitor.close_instance(instance)
            except Exception:
                pass
            with self._instances_lock:
                if instance in self._instances:
                    self._instances.remove(instance)
            self._single_instance = None

    def _scan_instances(self) -> None:
        """
        Poll all registered instances for failures or stop signal.

        Exits normally (pass) when:
          - test_duration_minutes elapsed with no failures, OR
          - stop() was called externally.

        Raises:
            DiskerciseTestFailedError: If an Operation Failure popup is detected.
            DiskerciseTimeoutError: If any instance window disappears unexpectedly.
        """
        duration_secs = self._config['test_duration_minutes'] * 60
        interval = self._config['check_interval_seconds']
        start_time = time.monotonic()
        retry_count = 0
        max_retry = 3

        logger.info(
            f"DiskerciseController: scanning {len(self._instances)} instance(s), "
            f"duration={duration_secs}s"
        )

        while not self._stop_event.is_set():
            with self._instances_lock:
                instances = list(self._instances)

            # Check for Operation Failure popups
            failed, msg = self._monitor.has_any_failure_popup(instances)
            if failed:
                raise DiskerciseTestFailedError(f"Operation Failure detected: {msg}")

            # Check all windows still exist
            for inst in instances:
                if not self._monitor.window_exists(inst, timeout=10):
                    retry_count += 1
                    logger.warning(
                        f"DiskerciseController: window not found (retry {retry_count}/{max_retry})"
                    )
                    if retry_count > max_retry:
                        raise DiskerciseTimeoutError(
                            "Diskercise window disappeared (retries exceeded)"
                        )
                else:
                    retry_count = 0

            # Check duration
            elapsed = time.monotonic() - start_time
            if elapsed >= duration_secs:
                logger.info("DiskerciseController: test duration elapsed — stopping")
                for inst in instances:
                    try:
                        self._monitor.click_stop(inst)
                    except Exception:
                        pass
                break

            time.sleep(interval)

        if self._stop_event.is_set():
            logger.info("DiskerciseController: stop event set — exiting scan")
