"""
Diskercise UI Monitor

This module provides UI monitoring and interaction for the Diskercise test tool.
Uses pywinauto win32 backend to control Diskercise.exe windows.
"""

import time
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

try:
    from PIL import ImageGrab as _ImageGrab
except ImportError:
    _ImageGrab = None

try:
    from pywinauto import Application
    from pywinauto.findwindows import ElementNotFoundError
    from pywinauto.timings import TimeoutError as PywinautoTimeoutError
except ImportError:
    # Allow import even if pywinauto not installed (for unit testing)
    Application = None
    ElementNotFoundError = Exception
    PywinautoTimeoutError = Exception

from .exceptions import DiskerciseUIError, DiskerciseTimeoutError


class DiskerciseInstance:
    """Represents a single running Diskercise.exe process and its window."""

    def __init__(self, app: Any, window: Any, exe_path: str):
        self.app = app
        self.window = window
        self.exe_path = exe_path


class DiskerciseUIMonitor:
    """
    UI monitor for Diskercise test tool using pywinauto win32 backend.

    Supports both single-window and multi-window (multi-instance) operation.
    Each instance corresponds to a separately launched Diskercise.exe process.

    Example:
        >>> monitor = DiskerciseUIMonitor()
        >>> instance = monitor.launch(exe_path=r'C:\\tools\\Diskercise\\Diskercise.exe')
        >>> monitor.set_gui_config(instance, config)
        >>> monitor.click_start(instance)
        >>> # ... poll for failures ...
        >>> monitor.click_stop(instance)
        >>> monitor.close_instance(instance)
    """

    WINDOW_TITLE_RE = 'Diskercise'
    ADV_TITLE_RE = 'Advance Settings'

    def __init__(
        self,
        window_wait_timeout: int = 30,
        ui_retry_max: int = 3,
        screenshot_dir: str = '',
    ):
        """
        Initialize the UI monitor.

        Args:
            window_wait_timeout: Seconds to wait for window to become enabled.
            ui_retry_max: Number of retry attempts for button clicks.
            screenshot_dir: Directory to save screenshots (empty = disabled).
        """
        if Application is None:
            raise ImportError("pywinauto is required for DiskerciseUIMonitor")
        self.window_wait_timeout = window_wait_timeout
        self.ui_retry_max = ui_retry_max
        self._screenshot_dir: str = screenshot_dir

    # ------------------------------------------------------------------ #
    #  Screenshot + topology helpers
    # ------------------------------------------------------------------ #

    def take_screenshot(self, label: str) -> Optional[Path]:
        """Capture a full-screen screenshot and save to screenshot_dir.

        Only captures when screenshot_dir is set and PIL is available.

        Args:
            label: Short descriptive label embedded in the filename.

        Returns:
            Path to the saved file, or None if skipped / failed.
        """
        if not self._screenshot_dir or _ImageGrab is None:
            return None
        try:
            Path(self._screenshot_dir).mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%H%M%S_%f")[:10]
            safe = label.replace(" ", "_").replace("/", "_").replace(":", "")[:40]
            path = Path(self._screenshot_dir) / f"{ts}_{safe}.png"
            img = _ImageGrab.grab()
            img.save(str(path))
            logger.info(f"[SCREENSHOT] {path.name}")
            return path
        except Exception as exc:
            logger.warning(f"[SCREENSHOT] Failed ({label}): {exc}")
            return None

    def log_topology(self, window: Any, label: str) -> None:
        """Log DEBUG-level snapshot of all UI controls in *window*.

        Zero overhead when effective log level is above DEBUG.
        Mirrors the log_topology pattern in winpvt.ui_monitor.

        Args:
            window: A pywinauto window wrapper to walk.
            label: Short context string for the log entry.
        """
        if not logger.isEnabledFor(10):   # logging.DEBUG == 10
            return
        try:
            lines = [f"[topology] {label}:"]
            for ctrl in window.descendants():
                try:
                    ct = ctrl.element_info.control_type
                    title = ctrl.window_text()
                    if title:
                        lines.append(f"  [{ct}] {title!r}")
                except Exception:
                    continue
            logger.debug("\n".join(lines))
        except Exception as exc:
            logger.debug(f"[topology] {label} — failed: {exc}")

    # ------------------------------------------------------------------ #
    #  Launch / Close
    # ------------------------------------------------------------------ #

    def launch(self, exe_path: str) -> 'DiskerciseInstance':
        """
        Launch Diskercise.exe and return a DiskerciseInstance.

        Args:
            exe_path: Absolute path to the Diskercise.exe to launch.

        Returns:
            DiskerciseInstance with app and window handles.

        Raises:
            DiskerciseUIError: If the window cannot be found after launch.
        """
        orig_cwd = os.getcwd()
        try:
            abs_path = os.path.abspath(exe_path)
            os.chdir(os.path.dirname(abs_path))
            app = Application(backend='win32').start(abs_path)
        finally:
            os.chdir(orig_cwd)

        try:
            window = app.window(title_re=self.WINDOW_TITLE_RE, found_index=0)
            window.wait('enabled', timeout=self.window_wait_timeout)
            window.set_focus()
        except (ElementNotFoundError, PywinautoTimeoutError, Exception) as e:
            try:
                app.kill()
            except Exception:
                pass
            raise DiskerciseUIError(f"Diskercise window not found after launch: {e}")

        logger.info(f"[UI] Diskercise window connected: {abs_path}")
        self.log_topology(window, "after launch")
        self.take_screenshot("after_launch")
        return DiskerciseInstance(app=app, window=window, exe_path=exe_path)

    def close_instance(self, instance: 'DiskerciseInstance') -> None:
        """
        Kill the Diskercise process for the given instance.

        Args:
            instance: The DiskerciseInstance to close.
        """
        try:
            instance.app.kill()
        except Exception:
            pass

    def close_all(self, instances: List['DiskerciseInstance']) -> None:
        """Kill all given instances."""
        for inst in instances:
            self.close_instance(inst)

    # ------------------------------------------------------------------ #
    #  Config
    # ------------------------------------------------------------------ #

    def set_gui_config(self, instance: 'DiskerciseInstance', config: Dict[str, Any]) -> None:
        """
        Apply configuration to the Diskercise GUI.

        Sets Thread, File Size, Access Size, R/W Ratio, Data Type, Buffered I/O,
        and Advance Settings (WriteSignatures, VerifyImmediate, PauseAllASAP, PulseCOM1).

        Args:
            instance: Target DiskerciseInstance.
            config: Config dict (keys from DiskerciseConfig.DEFAULT_CONFIG).

        Raises:
            DiskerciseUIError: If any GUI operation fails after retries.
        """
        w = instance.window
        try:
            w.set_focus()
            w["ThreadsEdit"].set_edit_text(config.get('thread_count', 1))
            time.sleep(0.5)
            w["File Size, MBEdit"].set_edit_text(config.get('file_size_mb', 0))
            time.sleep(0.5)
            w["Access Size, kBEdit"].set_edit_text(config.get('access_size_kb', 0))
            time.sleep(0.5)
            w["R/W RatioEdit"].set_edit_text(config.get('read_ratio', 0))
            time.sleep(0.5)
            w["R/W RatioEdit2"].set_edit_text(config.get('write_ratio', 0))
            time.sleep(0.5)
            self._set_checkbox(w["Buffered I/OCheckBox"], config.get('buffered_io', True))
            time.sleep(0.5)
            w["Data TypeComboBox"].select(config.get('data_type', 0))
            time.sleep(0.5)
        except Exception as e:
            raise DiskerciseUIError(f"Failed to set main GUI config: {e}")

        self._set_advance_settings(instance, config)
        logger.info("[UI] GUI config applied")
        self.log_topology(instance.window, "after set_gui_config")
        self.take_screenshot("after_set_gui_config")

    def _set_advance_settings(self, instance: 'DiskerciseInstance', config: Dict[str, Any]) -> None:
        """Open Advance Settings dialog and apply adv_* config values."""
        w = instance.window
        app = instance.app

        # Open the Advance Settings dialog
        opened = False
        for attempt in range(self.ui_retry_max):
            try:
                w.set_focus()
                w["Adv"].click_input()
                adv_win = app.window(title_re=self.ADV_TITLE_RE, found_index=0)
                adv_win.wait('enabled', timeout=10)
                opened = True
                break
            except Exception:
                time.sleep(0.5)

        if not opened:
            raise DiskerciseUIError("Failed to open Advance Settings dialog")

        try:
            self._set_checkbox(adv_win['Write &signatures on all sectors.'],
                               config.get('adv_write_signatures', True))
            time.sleep(0.5)
            self._set_checkbox(adv_win['Verify immediately after &writes.'],
                               config.get('adv_verify_immediate', True))
            time.sleep(0.5)
            self._set_checkbox(adv_win['&Pause all threads ASAP upon miscompare.'],
                               config.get('adv_pause_all_asap', True))
            time.sleep(0.5)
            self._set_checkbox(adv_win['Pulse &COM1 Tx line upon miscompare.'],
                               config.get('adv_pulse_com1', True))
            time.sleep(0.5)
        except Exception as e:
            raise DiskerciseUIError(f"Failed to set Advance Settings: {e}")

        # Close the dialog
        for attempt in range(self.ui_retry_max):
            try:
                adv_win['OK'].click()
                time.sleep(1)
                if not adv_win.exists(timeout=1):
                    break
            except Exception:
                break

    # ------------------------------------------------------------------ #
    #  Button clicks
    # ------------------------------------------------------------------ #

    def click_start(self, instance: 'DiskerciseInstance') -> None:
        """
        Click the Start button and wait for it to become disabled.

        Raises:
            DiskerciseUIError: If click fails after retries.
        """
        self._click_button_with_retry(instance.window, instance.window["Start"],
                                      wait_disabled=True)
        logger.info("[UI] Start button clicked")
        self.take_screenshot("after_click_start")

    def click_stop(self, instance: 'DiskerciseInstance') -> None:
        """
        Click the Stop button and wait for it to become disabled.

        Raises:
            DiskerciseUIError: If click fails after retries.
        """
        self._click_button_with_retry(instance.window, instance.window["Stop"],
                                      wait_disabled=True)
        logger.info("[UI] Stop button clicked")
        self.take_screenshot("after_click_stop")

    def _click_button_with_retry(self, window: Any, btn: Any, wait_disabled: bool = False) -> None:
        """Click a button with up to ui_retry_max attempts."""
        for attempt in range(self.ui_retry_max):
            try:
                window.set_focus()
                btn.click_input()
                if wait_disabled:
                    btn.wait_not("enabled")
                return
            except Exception:
                if attempt == self.ui_retry_max - 1:
                    raise DiskerciseUIError(
                        f"Button click failed after {self.ui_retry_max} attempts"
                    )

    # ------------------------------------------------------------------ #
    #  Status / Failure detection
    # ------------------------------------------------------------------ #

    def window_exists(self, instance: 'DiskerciseInstance', timeout: int = 10) -> bool:
        """
        Check whether the instance's window still exists.

        Args:
            instance: Target instance.
            timeout: pywinauto exists() timeout in seconds.

        Returns:
            True if window exists.
        """
        try:
            return instance.window.exists(timeout=timeout)
        except Exception:
            return False

    def has_failure_popup(self, instance: 'DiskerciseInstance') -> Tuple[bool, str]:
        """
        Scan all windows of the instance's app for an "Operation Failure" dialog.

        Args:
            instance: Target instance.

        Returns:
            (True, failure_title) if a failure popup is found, else (False, '').
        """
        try:
            wins = instance.app.windows()
            for w in wins:
                try:
                    name = w.element_info.name
                    if "Operation Failure" in name:
                        logger.error(f"[UI] Operation Failure popup detected: {name!r}")
                        self.take_screenshot("operation_failure_popup")
                        return True, name
                except Exception:
                    continue
        except Exception:
            pass
        return False, ''

    def has_any_failure_popup(self, instances: List['DiskerciseInstance']) -> Tuple[bool, str]:
        """
        Check all instances for an Operation Failure popup.

        Returns:
            (True, failure_title) on first match, else (False, '').
        """
        for inst in instances:
            found, msg = self.has_failure_popup(inst)
            if found:
                return True, msg
        return False, ''

    # ------------------------------------------------------------------ #
    #  Multi-instance helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def copy_exe_to_folder(src_exe: str, dest_folder: str) -> str:
        """
        Copy the Diskercise exe into dest_folder.

        Args:
            src_exe: Source path of Diskercise.exe.
            dest_folder: Destination directory (will be created if needed).

        Returns:
            Full path of the copied executable.
        """
        os.makedirs(dest_folder, exist_ok=True)
        dst = os.path.join(dest_folder, os.path.basename(src_exe))
        shutil.copyfile(src_exe, dst)
        return dst

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _set_checkbox(ctrl: Any, checked: bool) -> None:
        """Check or uncheck a checkbox control."""
        if checked:
            ctrl.check()
        else:
            ctrl.uncheck()
