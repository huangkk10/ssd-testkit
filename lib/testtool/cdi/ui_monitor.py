"""
CDI UI Monitor

Window monitoring and interaction using pywinauto for CrystalDiskInfo.
Handles: open, connect, text-log capture, screenshot capture, close.
"""

import os
import time
import json
from pathlib import Path
from typing import Optional, List

try:
    from pywinauto import Application, keyboard
    from pywinauto import timings
    from pywinauto.findwindows import ElementNotFoundError
    _PYWINAUTO_AVAILABLE = True
except ImportError:
    Application = None
    keyboard = None
    timings = None
    ElementNotFoundError = Exception
    _PYWINAUTO_AVAILABLE = False

from .exceptions import CDIUIError, CDITimeoutError
from lib.logger import get_module_logger

logger = get_module_logger(__name__)

_WINDOW_TITLE = ' CrystalDiskInfo '
_WINDOW_CLASS = '#32770'


class CDIUIMonitor:
    """
    UI monitor for CrystalDiskInfo (DiskInfo64.exe).

    Wraps all pywinauto interactions: launching the application,
    exporting the text log via Ctrl+T, capturing screenshots via the
    Disk menu, and closing the window.

    Example:
        >>> monitor = CDIUIMonitor()
        >>> monitor.open('./bin/CrystalDiskInfo/DiskInfo64.exe')
        >>> monitor.get_text_log('./testlog/DiskInfo.txt')
        >>> monitor.get_screenshot(
        ...     log_dir='./testlog',
        ...     prefix='',
        ...     drive_letter='C:',
        ...     diskinfo_json_path='./testlog/DiskInfo.json',
        ... )
        >>> monitor.close()
    """

    def __init__(
        self,
        window_title: str = _WINDOW_TITLE,
        window_class: str = _WINDOW_CLASS,
        save_dialog_timeout: float = 20,
        save_retry_max: int = 10,
    ):
        self.window_title = window_title
        self.window_class = window_class
        self.save_dialog_timeout = save_dialog_timeout
        self.save_retry_max = save_retry_max
        self._app = None
        self._window = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self, executable_path: str) -> None:
        """
        Launch CrystalDiskInfo and wait for its main window to be ready.

        Args:
            executable_path: Path to DiskInfo64.exe.

        Raises:
            CDIUIError: If pywinauto is not available or window does not appear.
        """
        if not _PYWINAUTO_AVAILABLE:
            raise CDIUIError("pywinauto is not installed")

        abs_exe = os.path.abspath(executable_path)
        logger.info(f"CDIUIMonitor: starting {abs_exe}")
        try:
            self._app = Application(backend='win32').start(abs_exe)
            self._window = self._app.window(
                title_re=self.window_title,
                class_name=self.window_class,
            )
            self._window.wait('ready', timeout=60)
            time.sleep(2)
            logger.info("CDIUIMonitor: window ready")
        except Exception as exc:
            raise CDIUIError(f"Failed to open CrystalDiskInfo: {exc}") from exc

    def connect(self) -> None:
        """
        Connect to an already-running CrystalDiskInfo window.

        Raises:
            CDIUIError: If pywinauto is not available or window not found.
        """
        if not _PYWINAUTO_AVAILABLE:
            raise CDIUIError("pywinauto is not installed")

        logger.info("CDIUIMonitor: connecting to existing window")
        try:
            self._app = Application(backend='win32').connect(
                title_re=self.window_title,
                class_name=self.window_class,
            )
            self._window = self._app.window(
                title_re=self.window_title,
                class_name=self.window_class,
            )
            self._window.wait('ready', timeout=60)
            logger.info("CDIUIMonitor: connected")
        except Exception as exc:
            raise CDIUIError(f"Failed to connect to CrystalDiskInfo: {exc}") from exc

    def close(self) -> None:
        """Kill the CrystalDiskInfo application."""
        time.sleep(2)
        if self._app:
            logger.info("CDIUIMonitor: killing application")
            try:
                self._app.kill()
            except Exception as exc:
                logger.warning(f"CDIUIMonitor: kill failed (may already be closed): {exc}")
        self._app = None
        self._window = None

    # ------------------------------------------------------------------
    # Text log export (Ctrl+T)
    # ------------------------------------------------------------------

    def get_text_log(self, save_path: str) -> None:
        """
        Export the CrystalDiskInfo text report via Ctrl+T → Save As dialog.

        Args:
            save_path: Absolute path where DiskInfo.txt should be saved.

        Raises:
            CDIUIError: If Save As dialog cannot be reached after retries.
        """
        if not self._window:
            raise CDIUIError("Not connected. Call open() or connect() first.")

        # Remove any stale copy so we can detect when the new file appears
        if os.path.exists(save_path):
            os.remove(save_path)
            time.sleep(2)

        # Trigger Ctrl+T and wait for Save As dialog
        save_app = self._trigger_save_dialog(
            trigger_keys='^T',
            dialog_title='Save As',
        )

        # Fill in the path and click Save, retrying until the file exists
        save_win = save_app.window(title='Save As', class_name=self.window_class)
        save_win.wait('ready', timeout=10)

        for attempt in range(self.save_retry_max):
            if os.path.exists(save_path):
                break
            save_win.set_focus()
            ctrl = save_win['Edit']
            ctrl.set_text(save_path)
            logger.info(f"CDIUIMonitor: saving text log → {save_path} (attempt {attempt + 1})")
            save_win['&Save'].click()
            time.sleep(1)
        else:
            raise CDIUIError(
                f"Failed to save text log to '{save_path}' after {self.save_retry_max} retries"
            )

        time.sleep(1)

    # ------------------------------------------------------------------
    # Screenshot export (Disk menu → Ctrl+S)
    # ------------------------------------------------------------------

    def get_screenshot(
        self,
        log_dir: str,
        prefix: str,
        drive_letter: str,
        diskinfo_json_path: str,
        png_name_override: str = '',
    ) -> None:
        """
        Capture screenshots for disk entries via the CrystalDiskInfo Disk menu.

        Args:
            log_dir:             Directory to save PNG files.
            prefix:              Filename prefix to prepend to each PNG.
            drive_letter:        If non-empty, only capture the drive matching
                                 this letter (e.g. 'C:').  Empty = capture all.
            diskinfo_json_path:  Path to the already-parsed DiskInfo.json, used
                                 to map drive letter → model/disk number.
            png_name_override:   If non-empty, use this name for the single PNG
                                 instead of auto-generating per disk entry.

        Raises:
            CDIUIError: If the Disk menu cannot be reached, or if saving fails.
        """
        if not self._window:
            raise CDIUIError("Not connected. Call open() or connect() first.")

        disk_menu = self._get_disk_menu()

        for item in disk_menu.items():
            # Decide whether to capture this item
            if drive_letter:
                model = self._get_drive_info_from_json(diskinfo_json_path, drive_letter, 'Model')
                disk_num = int(self._get_drive_info_from_json(diskinfo_json_path, drive_letter, 'DiskNum'))
                if not (model in str(item) and f'({disk_num})' in str(item)):
                    continue

            logger.info(f"CDIUIMonitor: selecting disk menu item {item.text()}")
            item.select()
            time.sleep(1)

            # Determine output filename
            if png_name_override:
                abs_name = os.path.abspath(
                    f"{log_dir}/{prefix}{png_name_override}"
                )
            else:
                item_text = item.text()
                for ch in (':', ']', '['):
                    item_text = item_text.replace(ch, '')
                abs_name = os.path.abspath(
                    f"{log_dir}/{prefix}DiskInfo_{item_text}.png"
                )

            if os.path.exists(abs_name):
                os.remove(abs_name)
                time.sleep(2)

            # Trigger Ctrl+S → Save As dialog
            save_app = self._trigger_save_dialog(
                trigger_keys='^S',
                dialog_title='Save As',
            )
            save_win = save_app.window(title='Save As', class_name=self.window_class)
            save_win.wait('ready', timeout=10)
            time.sleep(1)

            for attempt in range(self.save_retry_max):
                if os.path.exists(abs_name):
                    break
                save_win.set_focus()
                ctrl = save_win['Edit']
                ctrl.set_text(abs_name)
                logger.info(f"CDIUIMonitor: saving screenshot → {abs_name} (attempt {attempt + 1})")
                save_win['&Save'].click()
                time.sleep(1)
            else:
                if not os.path.exists(abs_name):
                    raise CDIUIError(
                        f"Unable to save screenshot to '{abs_name}' after {self.save_retry_max} retries"
                    )

            time.sleep(3)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trigger_save_dialog(self, trigger_keys: str, dialog_title: str):
        """
        Focus the CDI window, send keyboard shortcut, and wait for a
        named dialog to appear.  Retries up to save_retry_max times.

        Returns:
            pywinauto Application object connected to the dialog.

        Raises:
            CDIUIError: If the dialog never appears.
        """
        for attempt in range(self.save_retry_max):
            try:
                self._window.set_focus()
                keyboard.send_keys(trigger_keys)
                save_app = Application(backend='win32').connect(
                    title=dialog_title,
                    timeout=self.save_dialog_timeout,
                )
                return save_app
            except timings.TimeoutError:
                logger.warning(
                    f"CDIUIMonitor: '{dialog_title}' dialog not found "
                    f"(attempt {attempt + 1}/{self.save_retry_max})"
                )
                self._window.set_focus()

        raise CDIUIError(
            f"Could not find the '{dialog_title}' dialog after "
            f"{self.save_retry_max} attempts"
        )

    def _get_disk_menu(self):
        """
        Navigate to the Disk top-level menu and return its sub-menu.

        Retries up to save_retry_max times, reconnecting on failure.

        Raises:
            CDIUIError: If the menu is not reachable after retries.
        """
        for attempt in range(self.save_retry_max):
            try:
                time.sleep(2)
                app_menu = self._app.top_window().menu()
                disk_menu_path = app_menu.get_menu_path("Disk")
                if disk_menu_path:
                    self._window.set_focus()
                    return disk_menu_path[0].sub_menu()
            except Exception as exc:
                logger.warning(
                    f"CDIUIMonitor: Disk menu not accessible "
                    f"(attempt {attempt + 1}/{self.save_retry_max}): {exc}"
                )
                time.sleep(2)
                try:
                    self.connect()
                except CDIUIError:
                    pass

        raise CDIUIError(
            f"Could not access CrystalDiskInfo Disk menu after "
            f"{self.save_retry_max} attempts"
        )

    @staticmethod
    def _get_drive_info_from_json(json_path: str, drive_letter: str, key: str) -> str:
        """
        Read a single field for a drive from a DiskInfo JSON file.

        Args:
            json_path:    Path to DiskInfo.json.
            drive_letter: Drive letter to look up (e.g. 'C:').
            key:          Field to retrieve (e.g. 'Model', 'DiskNum').

        Returns:
            Field value as a string.

        Raises:
            CDIUIError: If the drive is not found in the JSON.
        """
        with open(json_path, newline='') as f:
            data = json.load(f)
        disks = data.get('disks', [])
        matches = [d for d in disks if drive_letter in d.get('Drive Letter', '')]
        if not matches:
            raise CDIUIError(
                f"Drive '{drive_letter}' not found in {json_path}"
            )
        return str(matches[0][key])
