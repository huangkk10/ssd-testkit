"""
WinPVT UI Monitor

pywinauto-based helpers for WinPVT UI automation:
- Full-screen screenshots with timestamped filenames
- DEBUG-level UI topology logging
- Startup dialog dismissal loop
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from lib.logger import get_module_logger

logger = get_module_logger(__name__)

try:
    from pywinauto import Application, Desktop  # noqa: F401
    from pywinauto.findwindows import ElementNotFoundError  # noqa: F401
    _PYWINAUTO_AVAILABLE = True
except ImportError:
    _PYWINAUTO_AVAILABLE = False

# Button labels to try (in priority order) when dismissing WinPVT startup dialogs.
# Affirmative actions first; Skip / Cancel / Close as last resort.
_DIALOG_BTNS = [
    "Accept", "Accept All", "Agree", "OK", "Yes", "Continue",
    "Proceed", "Next", "Skip", "Cancel", "Close",
]


class WinPVTUIMonitor:
    """UI automation helpers for WinPVT.

    Example::

        from lib.testtool.winpvt.ui_monitor import WinPVTUIMonitor
        monitor = WinPVTUIMonitor(Path('./testlog/screenshots'))
        monitor.take_screenshot('after_launch')
        monitor.dismiss_all_dialogs(app, main_handle, timeout=120)
    """

    def __init__(self, screenshot_dir: Path):
        self._screenshot_dir = Path(screenshot_dir)

    # ------------------------------------------------------------------
    # Screenshots
    # ------------------------------------------------------------------

    def take_screenshot(self, label: str) -> Optional[Path]:
        """Capture a full-screen screenshot and save it to the screenshot directory.

        The filename is ``HHMMSS_ff_<label>.png`` where ``ff`` are the first
        two digits of microseconds (ensures chronological sort order).

        Args:
            label: Short descriptive label embedded in the filename.

        Returns:
            Path to the saved file, or ``None`` if the capture failed.
        """
        try:
            from PIL import ImageGrab
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%H%M%S_%f")[:10]
            safe = (
                label.replace(" ", "_")
                     .replace("/", "_")
                     .replace(":", "")[:40]
            )
            path = self._screenshot_dir / f"{ts}_{safe}.png"
            img = ImageGrab.grab()
            img.save(str(path))
            logger.info(f"[SCREENSHOT] {path.name}")
            print(f"[SCREENSHOT] {path}")
            return path
        except Exception as exc:
            logger.warning(f"[SCREENSHOT] Failed ({label}): {exc}")
            return None

    # ------------------------------------------------------------------
    # Topology logging
    # ------------------------------------------------------------------

    def log_topology(self, window, label: str) -> None:
        """Log a DEBUG-level snapshot of all UI elements in *window*.

        Zero overhead when the effective log level is above DEBUG (10).
        Mirrors the ``_log_wac_topology`` pattern in
        ``lib/testtool/windows_adk/ui_runner.py``.

        Args:
            window: A pywinauto window wrapper whose descendants will be walked.
            label:  Short context string prepended to the log entry.
        """
        if not logger.isEnabledFor(10):  # logging.DEBUG == 10
            return
        try:
            lines = [f"[topology] {label}:"]
            for ctrl in window.descendants():
                try:
                    ct = ctrl.element_info.control_type
                    title = ctrl.window_text()
                    aid = getattr(ctrl.element_info, "automation_id", "") or ""
                    if title or aid:
                        row = f"  [{ct}] title={title!r}"
                        if aid:
                            row += f"  aid={aid!r}"
                        lines.append(row)
                except Exception:
                    continue
            logger.debug("\n".join(lines))
        except Exception as exc:
            logger.debug(f"[topology] {label} — failed: {exc}")

    # ------------------------------------------------------------------
    # Dialog dismissal
    # ------------------------------------------------------------------

    def dismiss_all_dialogs(self, app, main_handle: int,
                            timeout: int = 120) -> bool:
        """Poll for WinPVT startup dialogs and dismiss them.

        Scans ``app.windows()`` every 2 seconds, skips the main window
        (identified by *main_handle*), and for each visible secondary window
        tries every button in :data:`_DIALOG_BTNS` priority order.  Returns
        once 3 consecutive poll cycles find no dismissible windows.

        A screenshot is taken **before** and **after** each button click.
        The UI topology of every dialog is logged at DEBUG level.

        Args:
            app:         pywinauto ``Application`` object.
            main_handle: Win32 handle of the main WinPVT window to skip.
            timeout:     Maximum seconds before giving up.

        Returns:
            ``True`` if dialogs were cleared within *timeout*;
            ``False`` if the timeout expired.
        """
        if not _PYWINAUTO_AVAILABLE:
            logger.warning("[DIALOG] pywinauto not available — skipping dialog dismissal")
            return True

        consecutive_clean = 0
        required_clean = 3
        poll_interval = 2
        deadline = time.monotonic() + timeout
        iteration = 0

        logger.info(
            f"[DIALOG] Starting dialog-dismiss loop "
            f"(timeout={timeout}s, required_clean={required_clean})"
        )
        print(
            f"[DIALOG] Starting dialog-dismiss loop "
            f"(timeout={timeout}s, required_clean={required_clean})"
        )

        while time.monotonic() < deadline:
            iteration += 1
            dialog_found = False

            try:
                windows = app.windows()
            except Exception as exc:
                logger.warning(
                    f"[DIALOG] app.windows() failed (iter={iteration}): {exc}"
                )
                time.sleep(poll_interval)
                continue

            for win in windows:
                try:
                    handle = win.handle

                    # Skip idle main application windows (have MenuBar but no
                    # child [Window] modal). When a modal IS open, the main
                    # window will have child Window elements in its descendants.
                    try:
                        desc_types = {
                            d.element_info.control_type
                            for d in win.descendants()
                        }
                        if 'MenuBar' in desc_types and 'Window' not in desc_types:
                            logger.debug(
                                f"[DIALOG] iter={iteration} "
                                f"skipping idle main window handle={handle}"
                            )
                            continue
                    except Exception:
                        pass

                    try:
                        visible = win.is_visible()
                    except Exception:
                        visible = True
                    if not visible:
                        continue

                    title = ""
                    try:
                        title = win.window_text()
                    except Exception:
                        pass

                    logger.info(
                        f"[DIALOG] iter={iteration} found window "
                        f"title={title!r} handle={handle}"
                    )
                    print(
                        f"[DIALOG] iter={iteration} found window "
                        f"title={title!r} handle={handle}"
                    )

                    self.log_topology(
                        win, f"dialog iter={iteration} title={title!r}")
                    self.take_screenshot(
                        f"dialog_{iteration:03d}_before_{title[:20]}")

                    # Enumerate all Button descendants, then match by priority
                    try:
                        all_buttons = {
                            b.window_text(): b
                            for b in win.descendants(control_type='Button')
                        }
                        logger.debug(
                            f"[DIALOG] iter={iteration} buttons found: "
                            f"{list(all_buttons.keys())}"
                        )
                        print(
                            f"[DIALOG] iter={iteration} buttons found: "
                            f"{list(all_buttons.keys())}"
                        )
                    except Exception as exc:
                        logger.warning(
                            f"[DIALOG] iter={iteration} "
                            f"descendants() failed: {exc}"
                        )
                        all_buttons = {}

                    for btn_title in _DIALOG_BTNS:
                        if btn_title not in all_buttons:
                            continue
                        try:
                            btn = all_buttons[btn_title]
                            logger.info(
                                f"[DIALOG] iter={iteration} "
                                f"clicking '{btn_title}' in {title!r}"
                            )
                            print(
                                f"[DIALOG] iter={iteration} "
                                f"clicking '{btn_title}' in {title!r}"
                            )
                            btn.click_input()
                            time.sleep(0.5)
                            self.take_screenshot(
                                f"dialog_{iteration:03d}_after_{btn_title}")
                            dialog_found = True
                            break
                        except Exception as exc:
                            logger.warning(
                                f"[DIALOG] iter={iteration} "
                                f"click '{btn_title}' failed: {exc}"
                            )

                    if dialog_found:
                        break

                except Exception as exc:
                    logger.debug(f"[DIALOG] window inspection error: {exc}")
                    continue

            if dialog_found:
                # After clicking any button, reset to -5 so we wait 5 more
                # clean cycles (~6 s) before declaring done. This gives the
                # application time to show follow-up dialogs (e.g. the WinPVT
                # "No AccessKey.txt" popup that appears after License Agreement).
                # Observed max follow-up gap is ~4 s; -2 provides ~6 s buffer.
                consecutive_clean = -2
            else:
                consecutive_clean += 1
                logger.debug(
                    f"[DIALOG] clean check {consecutive_clean}/{required_clean}"
                )
                print(f"[DIALOG] clean check {consecutive_clean}/{required_clean}")
                if consecutive_clean >= required_clean:
                    logger.info(
                        f"[DIALOG] No dialogs for {required_clean} consecutive "
                        f"checks — startup dialogs cleared"
                    )
                    print(
                        f"[DIALOG] Done — no dialogs for "
                        f"{required_clean} consecutive checks"
                    )
                    return True

            time.sleep(poll_interval)

        logger.warning(f"[DIALOG] Timed out after {timeout}s — some dialogs may remain")
        print(f"[DIALOG] WARNING: timed out after {timeout}s")
        return False
