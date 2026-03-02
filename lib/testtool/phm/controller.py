"""
PHM (Powerhouse Mountain) Controller

Threading-based controller for managing PHM test execution and monitoring.

Orchestrates all PHM sub-components:
  1. PHMProcessManager  — install / launch / terminate
  2. PHMUIMonitor       — set parameters, start/stop test, read status
  3. PHMLogParser       — parse HTML report to determine pass/fail
"""

import threading
import time
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure package root is importable when executed directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.logger import get_module_logger
from .config import PHMConfig
from .exceptions import (
    PHMError,
    PHMConfigError,
    PHMTimeoutError,
    PHMProcessError,
    PHMInstallError,
    PHMUIError,
    PHMLogParseError,
    PHMTestFailedError,
)
from .process_manager import PHMProcessManager
from .log_parser import PHMLogParser, PHMTestResult
from .ui_monitor import PHMUIMonitor

logger = get_module_logger(__name__)


class PHMController(threading.Thread):
    """
    Controller for PHM (Powerhouse Mountain) test execution.

    Inherits from :class:`threading.Thread`.  Call :meth:`start` to begin
    execution in a background thread and :meth:`join` to wait for it.

    Full workflow performed by :meth:`run`:

    1. Check if PHM is installed; install if ``auto_install=True`` and not found.
    2. Launch the PHM GUI.
    3. Wait for the window to appear.
    4. Set test parameters (cycles, duration, Modern Standby).
    5. Click Start.
    6. Poll until completion or timeout.
    7. Parse the HTML log report.
    8. Set :attr:`status` to ``True`` (PASS) or ``False`` (FAIL).

    Example:
        >>> from lib.testtool.phm import PHMController
        >>>
        >>> controller = PHMController(
        ...     installer_path='./bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe',
        ...     cycle_count=10,
        ...     enable_modern_standby=True,
        ...     log_path='./testlog/PHMLog',
        ...     timeout=7200,
        ... )
        >>> controller.start()
        >>> controller.join()
        >>> assert controller.status is True, f"PHM failed: {controller.error_count} errors"
    """

    def __init__(self, **kwargs):
        """
        Initialize PHM controller.

        All keyword arguments are merged into the default config via
        :class:`PHMConfig`.  Unknown keys raise :exc:`PHMConfigError`.

        Args:
            **kwargs: Any valid PHMConfig parameter (see :class:`PHMConfig`).

        Raises:
            PHMConfigError: If unknown or wrongly-typed parameters are passed.
        """
        super().__init__(daemon=True)

        # Build config
        self._config: Dict[str, Any] = PHMConfig.get_default_config()
        if kwargs:
            self._config = PHMConfig.merge_config(self._config, kwargs)

        # Thread control
        self._stop_event = threading.Event()

        # Result state (None = not finished, True = PASS, False = FAIL)
        self._status: Optional[bool] = None
        self._error_count: int = 0
        self._last_result: Optional[PHMTestResult] = None

        # Sub-components (created lazily in _build_components)
        self._process_manager: Optional[PHMProcessManager] = None
        self._ui_monitor: Optional[PHMUIMonitor] = None
        self._log_parser: PHMLogParser = PHMLogParser()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_config(self, **kwargs) -> None:
        """
        Update configuration parameters at runtime (before :meth:`start`).

        Args:
            **kwargs: Valid PHMConfig parameters to override.

        Raises:
            PHMConfigError: If any key is unknown or has the wrong type.
        """
        self._config = PHMConfig.merge_config(self._config, kwargs)

    # ------------------------------------------------------------------
    # Install helpers (convenience wrappers)
    # ------------------------------------------------------------------

    def is_installed(self) -> bool:
        """Return True if PHM is already installed."""
        return self._get_process_manager().is_installed()

    def install(self) -> bool:
        """
        Install PHM using the configured ``installer_path``.

        Returns:
            True if installation succeeded.

        Raises:
            PHMInstallError: If ``installer_path`` is empty or install fails.
        """
        installer = self._config.get('installer_path', '')
        if not installer:
            raise PHMInstallError(
                "installer_path is not set. "
                "Pass installer_path=... to PHMController()"
            )
        return self._get_process_manager().install(
            installer_path=installer,
            timeout=int(self._config.get('timeout', 600)),
        )

    def uninstall(self) -> bool:
        """
        Uninstall PHM.

        Returns:
            True if uninstallation succeeded.
        """
        return self._get_process_manager().uninstall(
            timeout=int(self._config.get('timeout', 120)),
        )

    # ------------------------------------------------------------------
    # Thread interface
    # ------------------------------------------------------------------

    @property
    def status(self) -> Optional[bool]:
        """
        Execution result.

        Returns:
            ``None``  — still running or not yet started.
            ``True``  — test passed.
            ``False`` — test failed or error occurred.
        """
        return self._status

    @property
    def error_count(self) -> int:
        """Number of errors detected in the last test run."""
        return self._error_count

    @property
    def last_result(self) -> Optional[PHMTestResult]:
        """The parsed :class:`PHMTestResult` from the last run, or ``None``."""
        return self._last_result

    def stop(self) -> None:
        """
        Signal the controller to stop execution gracefully.

        Sets the internal stop event; the running thread will exit its
        monitoring loop and attempt to stop the PHM process.
        """
        logger.info("PHMController: stop signal received")
        self._stop_event.set()

    def run(self) -> None:
        """Thread body.  Do not call directly — use :meth:`start`."""
        logger.info("PHMController: starting test execution")
        try:
            self._execute_test()
        except PHMTestFailedError as exc:
            logger.error(f"PHM test failed: {exc}")
            self._status = False
        except PHMTimeoutError as exc:
            logger.error(f"PHM timeout: {exc}")
            self._status = False
        except (PHMInstallError, PHMProcessError, PHMUIError) as exc:
            logger.error(f"PHM infrastructure error: {exc}")
            self._status = False
        except PHMError as exc:
            logger.error(f"PHM error: {exc}")
            self._status = False
        except Exception as exc:
            logger.error(f"PHMController unexpected error: {exc}", exc_info=True)
            self._status = False
        finally:
            self._cleanup()

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def _execute_test(self) -> None:
        """Orchestrate the full PHM test workflow."""
        cfg = self._config

        # --- Step 1: Ensure PHM is installed ---
        pm = self._get_process_manager()
        if not pm.is_installed():
            installer = cfg.get('installer_path', '')
            if not installer:
                raise PHMInstallError(
                    "PHM is not installed and installer_path is not configured."
                )
            logger.info("PHM not installed — running installer")
            pm.install(installer_path=installer, timeout=600)

        # --- Step 2: Launch GUI ---
        logger.info("Launching PHM GUI")
        pm.launch()

        # --- Step 3: Wait for window ---
        ui = self._get_ui_monitor()
        ui.wait_for_window(timeout=60)

        # --- Step 4: Configure parameters ---
        ui.set_cycle_count(cfg['cycle_count'])
        ui.set_test_duration(cfg['test_duration_minutes'])
        ui.set_modern_standby_mode(cfg['enable_modern_standby'])

        # --- Step 5: Take baseline screenshot ---
        if cfg.get('enable_screenshot'):
            self._take_screenshot('before_start')

        # --- Step 6: Start test ---
        ui.start_test()
        logger.info(
            f"PHM test started — cycles={cfg['cycle_count']}, "
            f"duration={cfg['test_duration_minutes']}min, "
            f"modern_standby={cfg['enable_modern_standby']}"
        )

        # --- Step 7: Monitor until done or stop/timeout ---
        timeout    = float(cfg['timeout'])
        interval   = float(cfg['check_interval_seconds'])
        elapsed    = 0.0
        while not self._stop_event.is_set() and elapsed < timeout:
            time.sleep(interval)
            elapsed += interval

            try:
                current_status = ui.get_current_status()
            except PHMUIError as exc:
                logger.warning(f"Could not read UI status: {exc}")
                current_status = ''

            if current_status.upper() in ('PASS', 'FAIL', 'COMPLETED', 'DONE'):
                logger.info(f"PHM UI reports: {current_status}")
                break
        else:
            if not self._stop_event.is_set():
                if cfg.get('enable_screenshot'):
                    self._take_screenshot('timeout')
                raise PHMTimeoutError(
                    f"PHM test did not complete in {timeout} seconds"
                )

        # --- Step 8: Screenshot on completion ---
        if cfg.get('enable_screenshot'):
            self._take_screenshot('after_completion')

        # --- Step 9: Parse HTML log ---
        log_dir = cfg.get('log_path', './testlog/PHMLog')
        report_path = self._find_latest_html_report(log_dir)

        if report_path:
            try:
                result = self._log_parser.parse_html_report(report_path)
                self._last_result = result
                self._error_count = len(result.errors)

                if result.status == 'PASS':
                    self._status = True
                    logger.info("PHM test result: PASS")
                elif result.status == 'FAIL':
                    self._status = False
                    raise PHMTestFailedError(
                        f"PHM test FAILED: {self._error_count} error(s) — "
                        + '; '.join(result.errors[:5])
                    )
                else:
                    logger.warning(f"PHM result UNKNOWN — treating as FAIL")
                    self._status = False
            except PHMLogParseError as exc:
                logger.error(f"Could not parse HTML report: {exc}")
                self._status = False
        else:
            logger.warning(f"No HTML report found in {log_dir} — cannot determine result")
            self._status = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_process_manager(self) -> PHMProcessManager:
        if self._process_manager is None:
            self._process_manager = PHMProcessManager(
                install_path=self._config['install_path'],
                executable_name=self._config['executable_name'],
            )
        return self._process_manager

    def _get_ui_monitor(self) -> PHMUIMonitor:
        if self._ui_monitor is None:
            self._ui_monitor = PHMUIMonitor(
                retry_max=self._config['ui_retry_max'],
                retry_interval=float(self._config['ui_retry_interval_seconds']),
            )
        return self._ui_monitor

    def _find_latest_html_report(self, log_dir: str) -> Optional[str]:
        """Return path of most-recently modified .html file in log_dir, or None."""
        path = Path(log_dir)
        if not path.exists():
            return None
        html_files = sorted(path.glob('*.html'), key=os.path.getmtime, reverse=True)
        return str(html_files[0]) if html_files else None

    def _take_screenshot(self, tag: str) -> None:
        """Attempt a screenshot; log warning on failure (never raises)."""
        try:
            screenshot_dir = self._config.get('screenshot_path', './testlog/PHMLog/screenshots')
            ts = int(time.time())
            path = str(Path(screenshot_dir) / f"phm_{tag}_{ts}.png")
            if self._ui_monitor and self._ui_monitor.is_connected:
                self._ui_monitor.take_screenshot(path)
        except Exception as exc:
            logger.warning(f"Screenshot '{tag}' failed: {exc}")

    def _cleanup(self) -> None:
        """Best-effort cleanup: disconnect UI, terminate process."""
        try:
            if self._ui_monitor and self._ui_monitor.is_connected:
                self._ui_monitor.disconnect()
        except Exception:
            pass

        try:
            if self._process_manager and self._process_manager.is_running():
                self._process_manager.terminate()
        except Exception:
            pass
