"""
PwrTest Controller

Threading-based controller for managing pwrtest.exe execution and monitoring.

pwrtest.exe is a Microsoft WDK tool that drives Windows into a sleep state
and wakes it up after a configurable delay.  It writes its results to
``pwrtestlog.log`` and ``pwrtestlog.xml`` in the working directory.

Typical usage::

    controller = PwrTestController(
        os_name='win11',
        os_version='25H2',
        cycle_count=1,
        wake_after_seconds=30,
    )
    controller.start()
    controller.join(timeout=300)
    print(controller.status)         # True = PASS, False = FAIL
    print(controller.result_summary)
"""

import os
import shutil
import subprocess
import threading
import time
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from lib.logger import get_module_logger
from .config import PwrTestConfig, PwrTestScenario
from .exceptions import (
    PwrTestError,
    PwrTestConfigError,
    PwrTestTimeoutError,
    PwrTestProcessError,
    PwrTestLogParseError,
    PwrTestTestFailedError,
)
from .log_parser import PwrTestLogParser, PwrTestTestResult

logger = get_module_logger(__name__)


class PwrTestController(threading.Thread):
    """
    Controller for pwrtest.exe sleep/resume cycle testing.

    Inherits from :class:`threading.Thread` — call :meth:`start` to run
    asynchronously, then :meth:`join` to wait for completion.

    The controller:

    1. Resolves the ``pwrtest.exe`` path from config
       (``executable_path`` or ``os_name`` + ``os_version``).
    2. Creates the output log directory.
    3. Launches ``pwrtest.exe /sleep /c:<n> /d:<n> /p:<n>``
       with cwd set to the log directory (so log files land there).
    4. Monitors the process with a timeout watchdog.
    5. After the process exits, parses ``pwrtestlog.log``.
    6. Sets :attr:`status` to ``True`` (PASS) or ``False`` (FAIL/error).

    Example::

        ctrl = PwrTestController(
            os_name='win11',
            os_version='25H2',
            cycle_count=1,
            delay_seconds=5,
            wake_after_seconds=30,
            log_path='./testlog/PwrTestLog',
        )
        ctrl.start()
        ctrl.join(timeout=120)
        assert ctrl.status is True

    Args:
        **kwargs: Any key from :attr:`PwrTestConfig.DEFAULT_CONFIG`.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(daemon=True)
        self._config: Dict[str, Any] = PwrTestConfig.get_default_config()
        if kwargs:
            self._config = PwrTestConfig.merge_config(self._config, kwargs)

        # Thread control
        self._stop_event = threading.Event()

        # Result state
        self._status: Optional[bool] = None
        self._error_count: int = 0
        self._result_summary: Dict[str, Any] = {}

        # Internal process handle (set during run)
        self._process: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def set_config(self, **kwargs: Any) -> None:
        """Update one or more config values at runtime (before :meth:`start`)."""
        self._config = PwrTestConfig.merge_config(self._config, kwargs)

    @property
    def status(self) -> Optional[bool]:
        """
        Execution status.

        Returns:
            ``None`` while the thread is running,
            ``True`` if the test passed,
            ``False`` if the test failed or an error occurred.
        """
        return self._status

    @property
    def error_count(self) -> int:
        """Number of errors detected in the log (after execution)."""
        return self._error_count

    @property
    def result_summary(self) -> Dict[str, Any]:
        """
        Structured result dict populated after the thread finishes.

        Keys: ``status``, ``cycles_attempted``, ``cycles_passed``,
        ``errors``, ``log_path``, ``exe_path``.
        """
        return self._result_summary

    def stop(self) -> None:
        """
        Signal the controller to stop.

        Sets the stop event so the monitor loop exits, then terminates
        the pwrtest.exe process if it is still running.
        """
        logger.info("PwrTestController: stop signal received")
        self._stop_event.set()
        self._terminate_process()

    # ------------------------------------------------------------------ #
    # Thread body                                                          #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Thread entry point.  Calls :meth:`_execute_test` and captures errors."""
        logger.info("PwrTestController: starting test execution")
        try:
            self._execute_test()
        except PwrTestTestFailedError as exc:
            logger.error(f"PwrTest test FAILED: {exc}")
            self._status = False
        except PwrTestTimeoutError as exc:
            logger.error(f"PwrTest timeout: {exc}")
            self._status = False
        except PwrTestError as exc:
            logger.error(f"PwrTest error: {exc}")
            self._status = False
        except Exception as exc:  # pragma: no cover
            logger.error(f"PwrTestController unexpected error: {exc}", exc_info=True)
            self._status = False

    # ------------------------------------------------------------------ #
    # Internal ─ execution                                                 #
    # ------------------------------------------------------------------ #

    def _execute_test(self) -> None:
        """Core execution logic (runs inside the thread)."""
        exe_path   = self._resolve_executable()
        log_dir    = self._prepare_log_dir()
        cmd        = self._build_command(exe_path, log_dir)
        timeout    = self._config['timeout_seconds']
        interval   = float(self._config['check_interval_seconds'])

        logger.info(f"PwrTestController: exe={exe_path}")
        logger.info(f"PwrTestController: cmd={' '.join(cmd)}")
        logger.info(f"PwrTestController: log_dir={log_dir}")

        # Run pwrtest from its own directory so it can load companion DLLs.
        # Pwrtest writes pwrtestlog.log/.xml into its cwd; we move them to
        # log_dir afterwards.
        exe_dir = exe_path.parent.resolve()
        log_dir_abs = log_dir.resolve()

        try:
            self._process = subprocess.Popen(
                cmd,
                cwd=str(exe_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise PwrTestProcessError(
                f"Failed to start pwrtest.exe '{exe_path}': {exc}"
            ) from exc

        logger.info(f"PwrTestController: PID={self._process.pid}")

        # --- Monitor loop with timeout watchdog ---
        elapsed = 0.0
        while not self._stop_event.is_set():
            ret = self._process.poll()
            if ret is not None:
                logger.info(
                    f"PwrTestController: process exited with return code {ret}"
                    f" (0x{ret & 0xFFFFFFFF:08X})"
                )
                # Log stdout/stderr for diagnostics (especially on failure)
                try:
                    stdout_data = self._process.stdout.read().decode(errors='replace').strip()
                    stderr_data = self._process.stderr.read().decode(errors='replace').strip()
                    if stdout_data:
                        logger.info(f"PwrTestController stdout:\n{stdout_data}")
                    if stderr_data:
                        logger.warning(f"PwrTestController stderr:\n{stderr_data}")
                except Exception:
                    pass
                break
            if elapsed >= timeout:
                self._terminate_process()
                raise PwrTestTimeoutError(
                    f"pwrtest.exe did not exit within {timeout}s"
                )
            time.sleep(interval)
            elapsed += interval

        # If stop was signalled externally, treat as failed
        if self._stop_event.is_set() and self._process.poll() is None:
            self._terminate_process()
            self._status = False
            self._result_summary = {
                'status': 'STOPPED',
                'cycles_attempted': 0,
                'cycles_passed': 0,
                'errors': ['Test was stopped externally'],
                'log_path': str(log_dir),
                'exe_path': str(exe_path),
            }
            return

        # --- Parse results ---
        self._parse_results(log_dir, exe_path)

    def _resolve_executable(self) -> Path:
        """Resolve and validate the pwrtest.exe path."""
        exe = PwrTestConfig.resolve_executable_path(self._config)
        if not exe.exists():
            raise PwrTestProcessError(
                f"pwrtest.exe not found at '{exe}'. "
                "Check 'executable_path', 'os_name', and 'os_version' config."
            )
        return exe

    def _prepare_log_dir(self) -> Path:
        """Create the log output directory if it does not exist."""
        log_dir = Path(self._config['log_path'])
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PwrTestProcessError(
                f"Cannot create log directory '{log_dir}': {exc}"
            ) from exc
        return log_dir

    def _build_command(self, exe_path: Path, log_dir: Path) -> List[str]:
        """Compose the pwrtest.exe CLI argument list."""
        cfg = self._config
        # Accept both PwrTestScenario enum and raw string
        scenario = cfg.get('scenario', PwrTestScenario.CS)
        scenario_val = scenario.value if isinstance(scenario, PwrTestScenario) else scenario
        prefix = cfg.get('log_prefix', '')
        cmd = [
            str(exe_path),
            f'/{scenario_val}',
            f"/c:{cfg['cycle_count']}",
            f"/d:{cfg['delay_seconds']}",
            f"/p:{cfg['wake_after_seconds']}",
            f"/lf:{log_dir.resolve()}",  # write logs directly to log_dir
        ]
        if prefix:
            cmd.append(f"/ln:{prefix}pwrtestlog")
        return cmd

    def _terminate_process(self) -> None:
        """Terminate the pwrtest.exe process if it is still running."""
        if self._process and self._process.poll() is None:
            logger.warning("PwrTestController: terminating pwrtest.exe")
            try:
                self._process.terminate()
                self._process.wait(timeout=10)
            except Exception:  # noqa: BLE001
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    def _parse_results(self, log_dir: Path, exe_path: Path) -> None:
        """Parse pwrtestlog.log inside *log_dir* and set :attr:`_status`."""
        log_file = log_dir / 'pwrtestlog.log'
        xml_file = log_dir / 'pwrtestlog.xml'

        parse_target = log_file if log_file.exists() else (
            xml_file if xml_file.exists() else None
        )

        if parse_target is None:
            logger.error(
                "PwrTestController: neither pwrtestlog.log nor pwrtestlog.xml "
                f"found in '{log_dir}'"
            )
            self._status = False
            self._result_summary = {
                'status': 'UNKNOWN',
                'cycles_attempted': 0,
                'cycles_passed': 0,
                'errors': [f'Log file not found in {log_dir}'],
                'log_path': str(log_dir),
                'exe_path': str(exe_path),
            }
            return

        try:
            parser = PwrTestLogParser()
            result: PwrTestTestResult = parser.parse_report(str(parse_target))
        except PwrTestLogParseError as exc:
            logger.error(f"PwrTestController: log parse error: {exc}")
            self._status = False
            self._result_summary = {
                'status': 'PARSE_ERROR',
                'cycles_attempted': 0,
                'cycles_passed': 0,
                'errors': [str(exc)],
                'log_path': str(log_dir),
                'exe_path': str(exe_path),
            }
            return

        self._error_count = len(result.errors)
        self._status = (result.status == 'PASS')
        self._result_summary = {
            'status':           result.status,
            'cycles_attempted': result.total_cycles,
            'cycles_passed':    result.completed_cycles,
            'errors':           result.errors,
            'log_path':         str(log_dir),
            'exe_path':         str(exe_path),
        }

        if not self._status:
            raise PwrTestTestFailedError(
                f"pwrtest.exe reported '{result.status}' "
                f"({result.completed_cycles}/{result.total_cycles} cycles completed). "
                f"Errors: {result.errors}"
            )

        logger.info(
            f"PwrTestController: PASS — "
            f"{result.completed_cycles}/{result.total_cycles} cycle(s) completed"
        )
