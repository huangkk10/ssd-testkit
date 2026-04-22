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
        self.pvt_file: str = cfg['pvt_file']
        self.dialog_dismiss_timeout: int = int(cfg['dialog_dismiss_timeout'])
        self.window_wait_timeout: int = int(cfg['window_wait_timeout'])

        self._status: Optional[bool] = None
        self._error_message: str = ""
        self._cycles: int = 0
        self._stop_event = threading.Event()

        # Set by setup_phase(); used by the thread in run()
        self._app = None
        self._monitor: Optional[WinPVTUIMonitor] = None

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

    def close_app(self) -> None:
        """Terminate the WinPVT process tree.

        Attempts a graceful close via Alt+F4 on the main window first; then
        uses ``taskkill /F /T`` to forcefully terminate the entire process
        tree (parent + all child processes).  This ensures child WinPVT.exe
        processes (which own dialogs) are also killed.
        Safe to call even if the process has already exited.
        """
        import subprocess

        if self._app is None:
            return
        pid = None
        try:
            pid = self._app.process
        except Exception:
            pass

        # Graceful close attempt
        try:
            windows = self._app.windows()
            if windows:
                try:
                    windows[0].type_keys('%{F4}')
                    time.sleep(5)
                except Exception:
                    pass
        except Exception:
            pass

        # Kill entire process tree so child WinPVT.exe dialogs are also terminated
        if pid:
            try:
                result = subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(pid)],
                    capture_output=True,
                )
                logger.info(f"[WINPVT] taskkill /F /T /PID {pid} → exit {result.returncode}")
            except Exception as exc:
                logger.warning(f"[WINPVT] taskkill failed: {exc}")

        # Fallback: kill by image name to catch any remaining instances
        try:
            subprocess.run(
                ['taskkill', '/F', '/IM', 'WinPVT.exe'],
                capture_output=True,
            )
        except Exception:
            pass

        logger.info("[WINPVT] WinPVT process tree terminated")

    @property
    def status(self) -> Optional[bool]:
        """``None`` while running, ``True`` on pass, ``False`` on failure."""
        return self._status

    @property
    def error_message(self) -> str:
        """Human-readable failure reason, or empty string on success."""
        return self._error_message

    @property
    def cycles(self) -> int:
        """Number of completed cycles read from WinPVT StatusBar."""
        return self._cycles

    # ------------------------------------------------------------------
    # Two-phase public API
    # ------------------------------------------------------------------

    def setup_phase(self) -> None:
        """Phase 1 (synchronous): launch WinPVT and dismiss all startup dialogs.

        Call this from test_05.  After it returns the WinPVT main window is
        idle and ready to load a test plan.  The internal ``_app`` and
        ``_monitor`` objects are stored for use by the thread in
        :meth:`run` (Phase 2).

        Raises:
            WinPVTUIError:     pywinauto not available, window not found, etc.
            WinPVTProcessError: executable missing or launch failure.
        """
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

        main_window, main_handle = self._wait_for_main_window(
            app, monitor, self.window_wait_timeout
        )
        monitor.take_screenshot("launch_main_window")
        monitor.log_topology(main_window, "after launch")

        logger.info("[WINPVT] Dismissing startup dialogs...")
        print("[WINPVT] Dismissing startup dialogs...")
        monitor.dismiss_all_dialogs(
            app, main_handle, timeout=self.dialog_dismiss_timeout
        )
        monitor.take_screenshot("after_dialogs_cleared")
        logger.info("[WINPVT] Startup dialogs cleared — WinPVT main window ready")
        print("[WINPVT] Startup dialogs cleared — WinPVT main window ready")

        # Store for Phase 2 (thread)
        self._app = app
        self._monitor = monitor

    # ------------------------------------------------------------------
    # Thread body  (Phase 2)
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Phase 2 (threaded): open test plan, click GO, wait, check results.

        Call :meth:`setup_phase` first, then ``ctrl.start()`` to kick off
        this thread.
        """
        try:
            self._run_test_phase()
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

    def _run_test_phase(self) -> None:
        """Phase 2 body: open .pvt, click GO, wait for completion, check results."""
        if self._app is None or self._monitor is None:
            raise WinPVTProcessError(
                "setup_phase() must be called before starting the test thread"
            )

        app = self._app
        monitor = self._monitor

        # Pre-run residual dialog flush: WinPVT sometimes shows dialogs AFTER
        # setup_phase's dismiss loop exits (e.g., "No AccessKey.txt" popup appears
        # after full initialization, just after the main window becomes visible).
        # This flush catches those late-appearing dialogs before we try to open
        # the test plan. Takes ~6 s if no dialog is present (3 clean checks × 2 s).
        logger.info("[WINPVT] Pre-run dialog flush (residual startup dialogs)...")
        print("[WINPVT] Pre-run dialog flush...")
        monitor.dismiss_all_dialogs(app, 0, timeout=30)

        # -- Load test plan and click GO ----------------------------------
        logger.info("[WINPVT] Loading test plan and starting test...")
        print("[WINPVT] Loading test plan and starting test...")
        self._start_test(app, monitor)

        # -- Wait for process to finish -----------------------------------
        try:
            self._wait_for_completion(app, monitor)
        finally:
            # Read Cycles from StatusBar before screenshotting final state
            self._cycles = self._read_statusbar_cycles(app)
            logger.info(f"[WINPVT] StatusBar Cycles: {self._cycles}")
            print(f"[WINPVT] StatusBar Cycles: {self._cycles}")
            monitor.take_screenshot("final_state")

        # -- Inspect result files -----------------------------------------
        self._check_results()

        logger.info("[WINPVT] WinPVT Standby Critical completed successfully")
        print("[WINPVT] WinPVT Standby Critical completed successfully")

    # ------------------------------------------------------------------
    # Test execution helpers
    # ------------------------------------------------------------------

    def _get_idle_main_window(self, app):
        """Return the WinPVT idle main window (has MenuBar, no modal child Window)."""
        for w in app.windows():
            try:
                title = w.window_text()
                if 'WinPVT' not in title:
                    continue
                desc_types = {d.element_info.control_type for d in w.descendants()}
                if 'MenuBar' in desc_types and 'Window' not in desc_types:
                    return w
            except Exception:
                continue
        return None

    def _open_test_plan(self, app, monitor: WinPVTUIMonitor) -> None:
        """Click the Open toolbar button, fill the pvt file path, and confirm."""
        pvt_path = self.pvt_file
        logger.info(f"[WINPVT] Opening test plan: {pvt_path}")
        print(f"[WINPVT] Opening test plan: {pvt_path}")

        # Get idle main window
        main_win = self._get_idle_main_window(app)
        if main_win is None:
            raise WinPVTUIError("Cannot find WinPVT idle main window for Open")

        # Click the toolbar Open button (aid='59392' contains it; avoid DropDown variants)
        try:
            toolbar_btns = {
                b.element_info.automation_id or b.window_text(): b
                for b in main_win.descendants(control_type='Button')
            }
            # Find 'Open' button that is NOT a DropDown (aid != 'DropDown')
            open_btn = None
            for b in main_win.descendants(control_type='Button'):
                try:
                    if (b.window_text() == 'Open'
                            and b.element_info.automation_id != 'DropDown'):
                        open_btn = b
                        break
                except Exception:
                    continue
            if open_btn is None:
                raise WinPVTUIError("Cannot find toolbar Open button in WinPVT main window")
            open_btn.click_input()
        except WinPVTUIError:
            raise
        except Exception as exc:
            raise WinPVTUIError(f"Failed to click Open button: {exc}") from exc

        monitor.take_screenshot("open_test_plan_dialog")

        # Wait for file dialog — search by title or by presence of File name Edit + Open btn
        deadline = time.monotonic() + 15
        file_dialog = None
        while time.monotonic() < deadline:
            try:
                for w in app.windows():
                    # Search top-level windows and their child [Window] descendants
                    candidates = [w]
                    try:
                        candidates += list(w.descendants(control_type='Window'))
                    except Exception:
                        pass
                    for cand in candidates:
                        try:
                            title = cand.window_text() or ''
                        except Exception:
                            continue
                        # Match by title keyword or by structure (has File name Edit)
                        if 'WinPVT Test Plan' in title or 'Test Plan' in title:
                            file_dialog = cand
                            break
                    if file_dialog:
                        break
                if file_dialog:
                    break
            except Exception:
                pass
            time.sleep(0.5)

        if file_dialog is None:
            monitor.take_screenshot("open_dialog_not_found")
            raise WinPVTUIError("WinPVT Test Plan file dialog did not appear")

        # Fill the file path using descendants() — file_dialog may be a UIAWrapper
        # (no child_window() available), so we iterate descendants directly.
        try:
            filename_edit = None
            confirm_btn = None
            for d in file_dialog.descendants():
                try:
                    ct = d.element_info.control_type
                    aid = getattr(d.element_info, 'automation_id', '') or ''
                    ttl = d.window_text()
                    if ct == 'Edit' and (ttl == 'File name:' or aid == '1148'):
                        filename_edit = d
                    if ct == 'Button' and aid == '1' and ttl == 'Open':
                        confirm_btn = d
                except Exception:
                    continue

            if filename_edit is None:
                raise WinPVTUIError(
                    "Cannot find 'File name:' edit box in file dialog")
            if confirm_btn is None:
                raise WinPVTUIError(
                    "Cannot find Open confirm button (aid=1) in file dialog")

            filename_edit.set_edit_text(pvt_path)
            time.sleep(0.3)
            confirm_btn.click_input()
        except WinPVTUIError:
            monitor.take_screenshot("open_dialog_fill_failed")
            raise
        except Exception as exc:
            monitor.take_screenshot("open_dialog_fill_failed")
            raise WinPVTUIError(f"Failed to fill/confirm file dialog: {exc}") from exc

        # Wait for dialog to close
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                if not file_dialog.exists():
                    break
            except Exception:
                break
            time.sleep(0.5)

        monitor.take_screenshot("after_test_plan_loaded")
        logger.info("[WINPVT] Test plan loaded")
        print("[WINPVT] Test plan loaded")

    def _click_go(self, app, monitor: WinPVTUIMonitor) -> None:
        """Click the Run (GO) toolbar button to start the WinPVT test."""
        logger.info("[WINPVT] Clicking GO (Run) to start test...")
        print("[WINPVT] Clicking GO (Run) to start test...")

        main_win = self._get_idle_main_window(app)
        if main_win is None:
            raise WinPVTUIError("Cannot find WinPVT idle main window for GO")

        try:
            run_btn = None
            for b in main_win.descendants(control_type='Button'):
                try:
                    if b.window_text() == 'Run':
                        run_btn = b
                        break
                except Exception:
                    continue
            if run_btn is None:
                raise WinPVTUIError("Cannot find Run/GO button in WinPVT toolbar")
            run_btn.click_input()
        except WinPVTUIError:
            raise
        except Exception as exc:
            raise WinPVTUIError(f"Failed to click Run/GO button: {exc}") from exc

        time.sleep(1)
        monitor.take_screenshot("after_go_clicked")
        logger.info("[WINPVT] GO clicked — test running")
        print("[WINPVT] GO clicked — test running")

    def _start_test(self, app, monitor: WinPVTUIMonitor) -> None:
        """Open the .pvt test plan and click GO to start the WinPVT test."""
        self._open_test_plan(app, monitor)
        self._click_go(app, monitor)

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

    def _wait_for_completion(self, app,
                              monitor: WinPVTUIMonitor) -> None:
        """Wait for WinPVT to finish by detecting the Test Summary dialog.

        WinPVT shows a "Test Summary" modal dialog when the test ends; the
        process stays alive until the user clicks OK.  We poll for that
        dialog, screenshot it, parse the pass/fail result, click OK, and
        then return.  If the process exits before the dialog appears (crash
        or forced stop) we also return early.
        """
        logger.info(
            f"[WINPVT] Waiting for completion (timeout={self.timeout_minutes}min)..."
        )
        print(
            f"[WINPVT] Waiting for completion (timeout={self.timeout_minutes}min)..."
        )

        import psutil
        pid = app.process
        deadline = time.monotonic() + self.timeout_seconds

        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                raise WinPVTProcessError("Stopped during wait for completion")

            # Check 1: Test Summary dialog (appears after test ends)
            try:
                for w in app.windows():
                    candidates = [w]
                    try:
                        candidates += list(w.descendants(control_type='Window'))
                    except Exception:
                        pass
                    for cand in candidates:
                        try:
                            if (cand.window_text() or '') == 'Test Summary':
                                self._handle_test_summary_dialog(
                                    cand, monitor, app)
                                return
                        except Exception:
                            continue
            except Exception:
                pass

            # Check 2: Global Information table shows Status='Completed'
            suite_info = self._read_suite_status(app)
            if suite_info.get('status') == 'Completed':
                errors = suite_info.get('errors', 0)
                warnings = suite_info.get('warnings', 0)
                logger.info(
                    f"[WINPVT] Table: Status=Completed, "
                    f"Errors={errors}, Warnings={warnings}"
                )
                print(
                    f"[WINPVT] Table: Status=Completed, "
                    f"Errors={errors}, Warnings={warnings}"
                )
                monitor.take_screenshot("completion_from_table")
                if errors > 0:
                    raise WinPVTTestFailedError(
                        f"WinPVT completed with {errors} error(s)"
                    )
                return

            # Check 3: process exited on its own (crash / early stop)
            if not psutil.pid_exists(pid):
                logger.warning(
                    "[WINPVT] Process exited without showing Test Summary dialog"
                )
                return

            time.sleep(5)

        monitor.take_screenshot("timeout_final")
        raise WinPVTTimeoutError(
            f"WinPVT did not finish within {self.timeout_minutes} minutes"
        )

    def _read_statusbar_cycles(self, app) -> int:
        """Read the Cycles counter from the WinPVT StatusBar.

        The StatusBar contains Text elements with titles like
        ``'Cycles: 00000001'``.  Returns the integer value, or 0 if
        the element cannot be found or parsed.
        """
        try:
            for w in app.windows():
                for d in w.descendants(control_type='Text'):
                    try:
                        t = d.window_text() or ''
                        if t.startswith('Cycles:'):
                            return int(t.split(':', 1)[1].strip())
                    except Exception:
                        continue
        except Exception:
            pass
        return 0

    def _read_suite_status(self, app) -> dict:
        """Read Errors, Warnings and Status from the Global Information table.

        The table columns are: Test Suites | Iterations | Errors | Warnings | Status.
        Returns a dict with keys ``status`` (str), ``errors`` (int),
        ``warnings`` (int); or an empty dict if the table cannot be read.
        """
        try:
            for w in app.windows():
                for li in w.descendants(control_type='ListItem'):
                    try:
                        # Collect non-empty text values from children
                        texts = []
                        for d in li.descendants():
                            t = (d.window_text() or '').strip()
                            if t:
                                texts.append(t)
                        # columns: Test Suites(0) Iterations(1) Errors(2) Warnings(3) Status(4)
                        # Find the index of a known Status value
                        for i, t in enumerate(texts):
                            if t in ('Completed', 'Running', 'Failed', 'Stopped', 'Aborted'):
                                errors = 0
                                warnings = 0
                                if i >= 2:
                                    try:
                                        errors = int(texts[i - 2])
                                    except (ValueError, IndexError):
                                        pass
                                if i >= 1:
                                    try:
                                        warnings = int(texts[i - 1])
                                    except (ValueError, IndexError):
                                        pass
                                return {
                                    'status': t,
                                    'errors': errors,
                                    'warnings': warnings,
                                }
                    except Exception:
                        continue
        except Exception:
            pass
        return {}

    def _handle_test_summary_dialog(self, dialog,
                                     monitor: WinPVTUIMonitor,
                                     app=None) -> None:
        """Read pass/fail from the Test Summary dialog, then click OK.

        Pass/fail is determined by reading the Global Information table
        (Errors column) rather than parsing dialog text, so that tests
        that complete with Warnings are not mis-reported as FAILED.

        Raises :exc:`WinPVTTestFailedError` on failure.
        """
        monitor.take_screenshot("test_summary_dialog")
        logger.info("[WINPVT] Test Summary dialog detected — reading result...")
        print("[WINPVT] Test Summary dialog detected — reading result...")

        # Primary: read Errors from the Global Information table
        errors = None
        warnings = None
        if app is not None:
            suite_info = self._read_suite_status(app)
            if suite_info:
                errors = suite_info['errors']
                warnings = suite_info['warnings']
                logger.info(
                    f"[WINPVT] Table: Errors={errors}, Warnings={warnings}, "
                    f"Status={suite_info.get('status')}"
                )

        # Fallback: scan dialog text for explicit ALL TESTS PASSED / FAILED
        dialog_passed = False
        dialog_failed = False
        try:
            for d in dialog.descendants():
                try:
                    t = (d.window_text() or '').upper()
                    if 'ALL TESTS PASSED' in t:
                        dialog_passed = True
                    if 'ALL TESTS FAILED' in t or '-- FAILED --' in t:
                        dialog_failed = True
                except Exception:
                    continue
        except Exception:
            pass

        # Determine final result
        if errors is not None:
            # Table read succeeded: Errors=0 → PASS, Errors>0 → FAIL
            failed = errors > 0
        else:
            # Table not available: fall back to dialog text
            failed = dialog_failed or not dialog_passed

        result_str = 'FAILED' if failed else 'PASSED'
        logger.info(f"[WINPVT] Test Summary result: {result_str}")
        print(f"[WINPVT] Test Summary result: {result_str}")

        # Dismiss the dialog by clicking OK
        try:
            for b in dialog.descendants(control_type='Button'):
                try:
                    if b.window_text() == 'OK':
                        b.click_input()
                        break
                except Exception:
                    continue
        except Exception as exc:
            logger.warning(f"[WINPVT] Could not click OK on Test Summary: {exc}")

        monitor.take_screenshot("after_test_summary_ok")

        if failed:
            err_detail = f" (Errors={errors})" if errors is not None else ""
            raise WinPVTTestFailedError(
                f"WinPVT test FAILED{err_detail}"
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
