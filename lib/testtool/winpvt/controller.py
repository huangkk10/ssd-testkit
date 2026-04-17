"""
WinPVT Controller

Threading-based controller for launching WinPVT, dismissing startup dialogs
via UI automation, waiting for test completion, and verifying results.
"""

import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from lib.logger import get_module_logger
from .config import WinPVTConfig
from .exceptions import (
    WinPVTConfigError,
    WinPVTProcessError,
    WinPVTTestFailedError,
    WinPVTTimeoutError,
    WinPVTUIError,
)
from .ui_monitor import WinPVTUIMonitor

logger = get_module_logger(__name__)

try:
    from pywinauto import Application
    _PYWINAUTO_AVAILABLE = True
except ImportError:
    Application = None
    _PYWINAUTO_AVAILABLE = False


class WinPVTController(threading.Thread):
    """Threading controller for WinPVT test execution.

    Launches WinPVT, dismisses all startup dialogs through UI automation,
    waits for the process to finish, and inspects result files.

    Example::

        from lib.testtool.winpvt import WinPVTController

        ctrl = WinPVTController(
            exe_path=r'C:\\Program Files\\HP\\WinPVT\\WinPVT.exe',
            result_path='./testlog/WinPVTResult',
            test_category='Standby',
            stress_level='Critical',
            timeout_minutes=120,
        )
        ctrl.start()
        ctrl.join(timeout=ctrl.timeout_seconds + 60)

        if ctrl.status is True:
            print("WinPVT PASSED")
        else:
            raise RuntimeError(ctrl.error_message)
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(daemon=True)
        cfg = WinPVTConfig.merge_config(WinPVTConfig.get_default_config(), kwargs)
        WinPVTConfig.validate_config(cfg)

        self.exe_path: str = cfg['exe_path']
        self.result_path: str = cfg['result_path']
        self.screenshot_dir: Path = Path(cfg['screenshot_dir'])
        self.test_category: str = cfg['test_category']
        self.stress_level: str = cfg['stress_level']
        self.timeout_minutes: int = int(cfg['timeout_minutes'])
        self.timeout_seconds: int = self.timeout_minutes * 60
        self.dialog_dismiss_timeout: int = int(cfg['dialog_dismiss_timeout'])
        self.window_wait_timeout: int = int(cfg['window_wait_timeout'])

        self._status: Optional[bool] = None
        self._error_message: str = ""
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_config(self, **kwargs: Any) -> None:
        """Override configuration parameters after construction."""
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise WinPVTConfigError(f"Unknown WinPVT config param: {key!r}")
            setattr(self, key, value)
        if 'timeout_minutes' in kwargs:
            self.timeout_seconds = self.timeout_minutes * 60

    def stop(self) -> None:
        """Signal the controller thread to stop."""
        self._stop_event.set()

    @property
    def status(self) -> Optional[bool]:
        """``None`` while running, ``True`` on pass, ``False`` on failure."""
        return self._status

    @property
    def error_message(self) -> str:
        """Human-readable failure reason, or empty string on success."""
        return self._error_message

    # ------------------------------------------------------------------
    # Thread body
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute WinPVT end-to-end inside the thread."""
        try:
            self._run_winpvt()
            self._status = True
        except (WinPVTTestFailedError, WinPVTTimeoutError,
                WinPVTProcessError, WinPVTUIError) as exc:
            self._status = False
            self._error_message = str(exc)
            logger.error(f"[WINPVT] {exc}")
        except Exception as exc:
            self._status = False
            self._error_message = f"Unexpected error: {exc}"
            logger.exception(f"[WINPVT] Unexpected error: {exc}")

    # ------------------------------------------------------------------
    # Private implementation
    # ------------------------------------------------------------------

    def _run_winpvt(self) -> None:
        if not _PYWINAUTO_AVAILABLE:
            raise WinPVTUIError(
                "pywinauto is not installed — cannot run WinPVT UI automation"
            )

        exe = Path(self.exe_path)
        if not exe.is_file():
            raise WinPVTProcessError(
                f"WinPVT executable not found: {self.exe_path}"
            )

        Path(self.result_path).mkdir(parents=True, exist_ok=True)
        monitor = WinPVTUIMonitor(self.screenshot_dir)

        # -- Launch -------------------------------------------------------
        logger.info(
            f"[WINPVT] Launching: {self.exe_path} "
            f"(category={self.test_category}, level={self.stress_level}, "
            f"timeout={self.timeout_minutes}min)"
        )
        print(f"[WINPVT] Launching: {self.exe_path}")

        try:
            app = Application(backend='uia').start(str(exe))
        except Exception as exc:
            raise WinPVTProcessError(f"Failed to launch WinPVT: {exc}") from exc

        # -- Wait for the main window -------------------------------------
        main_window, main_handle = self._wait_for_main_window(
            app, monitor, self.window_wait_timeout
        )

        monitor.take_screenshot("launch_main_window")
        monitor.log_topology(main_window, "after launch")

        # -- Dismiss startup dialogs --------------------------------------
        logger.info("[WINPVT] Dismissing startup dialogs...")
        print("[WINPVT] Dismissing startup dialogs...")
        monitor.dismiss_all_dialogs(
            app, main_handle, timeout=self.dialog_dismiss_timeout
        )
        monitor.take_screenshot("after_dialogs_cleared")
        logger.info("[WINPVT] Startup dialogs cleared — WinPVT running")
        print("[WINPVT] Startup dialogs cleared — WinPVT running")

        # -- Wait for process to finish -----------------------------------
        self._wait_for_completion(app, main_window, monitor)
        monitor.take_screenshot("completion")

        # -- Inspect result files -----------------------------------------
        self._check_results()

        logger.info("[WINPVT] WinPVT Standby Critical completed successfully")
        print("[WINPVT] WinPVT Standby Critical completed successfully")

    def _wait_for_main_window(self, app, monitor: WinPVTUIMonitor,
                               timeout: int):
        """Wait for any window to appear in *app* within *timeout* seconds."""
        deadline = time.monotonic() + timeout
        logger.info("[WINPVT] Waiting for WinPVT main window...")
        print("[WINPVT] Waiting for WinPVT main window...")

        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                raise WinPVTProcessError("Stopped before window appeared")
            try:
                for w in app.windows():
                    try:
                        t = w.window_text()
                        if t:
                            logger.info(
                                f"[WINPVT] Window found: {t!r} handle={w.handle}"
                            )
                            print(f"[WINPVT] Window found: {t!r} handle={w.handle}")
                            return w, w.handle
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(1)

        monitor.take_screenshot("launch_failed_no_window")
        raise WinPVTUIError(
            f"WinPVT main window did not appear within {timeout}s"
        )

    def _wait_for_completion(self, app, main_window,
                              monitor: WinPVTUIMonitor) -> None:
        """Wait for the WinPVT process to exit."""
        logger.info(
            f"[WINPVT] Waiting for completion (timeout={self.timeout_minutes}min)..."
        )
        print(
            f"[WINPVT] Waiting for completion (timeout={self.timeout_minutes}min)..."
        )

        try:
            import psutil
            proc = psutil.Process(app.process)
            proc.wait(timeout=self.timeout_seconds)
            logger.info("[WINPVT] Process exited")
            print("[WINPVT] Process exited")
            return
        except Exception as exc:
            logger.warning(
                f"[WINPVT] psutil.wait exception ({exc}) — "
                "falling back to window-existence poll"
            )
            monitor.take_screenshot("wait_psutil_exception")

        # Fallback: poll main_window.exists()
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                raise WinPVTProcessError("Stopped during wait for completion")
            try:
                if not main_window.exists():
                    logger.info("[WINPVT] Main window closed")
                    return
            except Exception:
                return  # window gone
            time.sleep(5)

        monitor.take_screenshot("timeout_final")
        raise WinPVTTimeoutError(
            f"WinPVT did not finish within {self.timeout_minutes} minutes"
        )

    def _check_results(self) -> None:
        """Scan the result directory for FAILED indicators in XML files."""
        result_dir = Path(self.result_path)
        if not result_dir.exists():
            logger.warning(f"[WINPVT] Result directory not found: {result_dir}")
            return

        result_files = [str(f) for f in result_dir.rglob('*') if f.is_file()]
        logger.info(f"[WINPVT] Result files: {result_files}")
        print(f"[WINPVT] Result files: {result_files}")

        for f in result_dir.rglob('*.xml'):
            try:
                content = f.read_text(errors='replace')
                upper = content.upper()
                if 'FAILED' in upper or '<FAIL' in upper:
                    raise WinPVTTestFailedError(
                        f"WinPVT result indicates FAILED: {f.name}"
                    )
            except WinPVTTestFailedError:
                raise
            except Exception:
                pass
