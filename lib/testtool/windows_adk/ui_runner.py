"""
Windows ADK UI Runner

Encapsulates all pywinauto interactions with Windows Assessment Console (WAC).
Each method is a single UI action — no business logic lives here.

NOTE: All auto_id values below were verified on Windows 11 22H2/23H2 (build 22621).
      They are EXPECTED to be the same on 24H2 (build 26100) but must be confirmed
      on a real 24H2 machine before sign-off (see Phase 4 of the development plan).
"""

import os
import time
import traceback
from typing import Optional

import psutil
import pyautogui
import pyperclip
from pywinauto import Application, findwindows, keyboard, timings

from lib.logger import get_module_logger
from .exceptions import ADKUIError, ADKProcessError, ADKTimeoutError
from .result_reader import WACRunResult, wait_for_view_results, debug_enumerate_view_results

logger = get_module_logger(__name__)

# WAC window title pattern
_WAC_TITLE = "Windows Assessment Console"
_LAUNCHER_TITLE_RE = "Assessment Launcher -"

# Assessment GUID auto_id constants (verified on build 22621)
_AID_QUICKRUN_PANEL = (
    "AID_Action_Microsoft.Assessments.Administration"
    ".Presentation.QuickRunViewModel"
)
_AID_ASSESSMENT = {
    "bpfs":           "AID_QuickRun_Assessment_9aa625ba-0fc5-4aaa-ab13-6b1b1a29c2cf",
    "bpfb":           "AID_QuickRun_Assessment_5a7a1def-2e1f-4a7b-a792-ae5275b6ef92",
    "standby":        "AID_QuickRun_Assessment_d57b93b2-9103-4a98-a8b7-4ca7c5230bbb",
    "modern_standby": "AID_QuickRun_Assessment_ec65f64e-55b4-4abc-a196-4c30af672924",
    "hibernate":      "AID_QuickRun_Assessment_bb6ad2d4-d388-4657-abf4-b289ae7723f7",
}
_AID_QUICKRUN_RUN_BTN  = "AID_QuickRun_RunButton"
_AID_JOBVIEW_RUN_BTN   = "AID_JobView_RunButton"
_AID_START_BTN         = "okButton"
_AID_NAME_TEXTBOX      = "AID_NameItemTextBox"
_AID_COPY_DETAILS_BTN  = "copyAllButton"


class WACSessions:
    """Holds live pywinauto Application + window references."""
    app: Optional[object] = None
    window: Optional[object] = None


class UIRunner:
    """Stateful wrapper around pywinauto for WAC GUI interactions.

    Attributes:
        _session: Stores active Application and window objects.
    """

    def __init__(self):
        self._session = WACSessions()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self, wac_exe: str) -> None:
        """Launch WAC and wait for the main window to become visible."""
        logger.debug(f"Opening WAC: {wac_exe}")
        try:
            self._session.app = Application(backend="uia").start(wac_exe)
            self._session.window = self._session.app.window(title_re=_WAC_TITLE)
            time.sleep(2)
            while True:
                if self._session.window.exists():
                    self._session.window.maximize()
                    logger.debug("WAC window found and maximized")
                    break
                logger.debug("Waiting for WAC window to appear ...")
                time.sleep(2)
            logger.info("WAC opened successfully")
        except Exception as exc:
            raise ADKUIError(f"Failed to open WAC: {exc}") from exc

    def close(self) -> None:
        """Kill axe.exe (assessment engine) and the WAC process."""
        logger.debug("Closing WAC: killing axe.exe then WAC app")
        self._kill_process("axe.exe")
        try:
            if self._session.app:
                self._session.app.kill()
                logger.debug("WAC app killed")
        except Exception as exc:
            logger.error(f"Error closing WAC: {exc}")

    def connect(self) -> None:
        """Reconnect to an already-running WAC window (e.g. after reboot)."""
        logger.debug(f"Connecting to existing WAC window: title='{_WAC_TITLE}'")
        try:
            self._session.app = Application(backend="uia").connect(title=_WAC_TITLE)
            self._session.window = self._session.app.window(title=_WAC_TITLE)
            logger.debug("Connected to WAC window successfully")
        except Exception as exc:
            raise ADKUIError(f"Failed to connect to WAC: {exc}") from exc

    # ------------------------------------------------------------------
    # Assessment selection helpers (Quick Run panel)
    # ------------------------------------------------------------------

    def _open_quickrun_panel(self) -> None:
        """Click 'Run Individual Assessments' to open the Quick Run list."""
        logger.debug("Clicking 'Run Individual Assessments' panel")
        ctrl = self._session.window.child_window(
            title="Run Individual Assessments",
            auto_id=_AID_QUICKRUN_PANEL,
            control_type="ListItem",
        )
        ctrl.select()
        logger.debug("Quick Run panel opened, waiting for list to populate")
        time.sleep(2)

    def select_bpfs(self) -> None:
        """Select Boot Performance (Fast Startup) and click Run."""
        logger.debug("select_bpfs: opening Quick Run panel")
        self._open_quickrun_panel()
        logger.debug("select_bpfs: selecting 'Boot performance (Fast Startup)'")
        ctrl = self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            auto_id=_AID_ASSESSMENT["bpfs"],
            control_type="ListItem",
        )
        ctrl.select()
        logger.debug("select_bpfs: clicking Run button")
        self._session.window.child_window(
            title="Run", auto_id=_AID_QUICKRUN_RUN_BTN, control_type="Button"
        ).click()
        logger.debug("select_bpfs: Run clicked")

    def select_bpfs_num_iters(self, num_iters: int, auto_boot: bool) -> None:
        """Select BPFS with custom iteration count, then open the JobView Run."""
        self._open_quickrun_panel()
        ctrl = self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            auto_id=_AID_ASSESSMENT["bpfs"],
            control_type="ListItem",
        )
        ctrl.select()
        # Open Configure pane
        self._session.window.child_window(
            title="Configure",
            auto_id="AID_QuickRun_ConfigureAndRun",
            control_type="Hyperlink",
        ).invoke()
        # Select the assessment in Job Properties pane
        self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            auto_id=_AID_ASSESSMENT["bpfs"],
            control_type="ListItem",
        ).select()
        # Uncheck "Use recommended settings"
        self._session.window.child_window(
            title="Use recommended settings",
            auto_id="AID_AssessmentView_BenchmarkMode",
            control_type="CheckBox",
        ).click_input()
        # Set iteration count
        self._session.window.child_window(
            title="3",
            auto_id="AID_Parameter_Value_Iterations",
            control_type="Edit",
        ).set_edit_text(str(num_iters))
        # Optionally disable wake timers
        if not auto_boot:
            self._session.window.child_window(
                title="Use wake timers to automate boot (if supported)",
                auto_id="AID_Parameter_Value_waketimersupport",
                control_type="CheckBox",
            ).click_input()
        self._session.window.child_window(
            title="Run", auto_id=_AID_JOBVIEW_RUN_BTN, control_type="Button"
        ).click()

    def select_bpfb(self) -> None:
        """Select Boot Performance (Full Boot) and click Run."""
        logger.debug("select_bpfb: opening Quick Run panel")
        self._open_quickrun_panel()
        logger.debug("select_bpfb: selecting 'Boot performance (Full Boot)'")
        ctrl = self._session.window.child_window(
            title="Boot performance (Full Boot)",
            auto_id=_AID_ASSESSMENT["bpfb"],
            control_type="ListItem",
        )
        ctrl.select()
        logger.debug("select_bpfb: clicking Run button")
        self._session.window.child_window(
            title="Run", auto_id=_AID_QUICKRUN_RUN_BTN, control_type="Button"
        ).click()
        logger.debug("select_bpfb: Run clicked")

    def select_standby(self) -> None:
        """Select Standby Performance and click Run."""
        logger.debug("select_standby: opening Quick Run panel")
        self._open_quickrun_panel()
        logger.debug("select_standby: scrolling down to reveal Standby item")
        focus_ctrl = self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            auto_id=_AID_ASSESSMENT["bpfs"],
            control_type="ListItem",
        )
        focus_ctrl.select()
        focus_ctrl.set_focus()
        keyboard.send_keys("{PGDN}{PGDN}{PGDN}")
        logger.debug("select_standby: selecting 'Standby performance'")
        self._session.window.child_window(
            title="Standby performance",
            auto_id=_AID_ASSESSMENT["standby"],
            control_type="ListItem",
        ).select()
        logger.debug("select_standby: clicking Run button")
        self._session.window.child_window(
            title="Run", auto_id=_AID_QUICKRUN_RUN_BTN, control_type="Button"
        ).click()
        logger.debug("select_standby: Run clicked")

    def select_modern_standby(self) -> None:
        """Select Modern Standby Performance and click Run."""
        logger.debug("select_modern_standby: opening Quick Run panel")
        self._open_quickrun_panel()
        logger.debug("select_modern_standby: scrolling down to reveal Modern Standby item")
        focus_ctrl = self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            auto_id=_AID_ASSESSMENT["bpfs"],
            control_type="ListItem",
        )
        focus_ctrl.select()
        focus_ctrl.set_focus()
        keyboard.send_keys("{PGDN}{PGDN}{PGDN}")
        logger.debug("select_modern_standby: selecting 'Modern Standby Performance'")
        self._session.window.child_window(
            title="Modern Standby Performance",
            auto_id=_AID_ASSESSMENT["modern_standby"],
            control_type="ListItem",
        ).select()
        logger.debug("select_modern_standby: clicking Run button")
        self._session.window.child_window(
            title="Run", auto_id=_AID_QUICKRUN_RUN_BTN, control_type="Button"
        ).click()
        logger.debug("select_modern_standby: Run clicked")

    def select_hibernate(self) -> None:
        """Select Hibernate Performance and click Run."""
        logger.debug("select_hibernate: opening Quick Run panel")
        self._open_quickrun_panel()
        focus_ctrl = self._session.window.child_window(
            auto_id=_AID_QUICKRUN_PANEL,
            control_type="ListItem",
        )
        focus_ctrl.set_focus()
        logger.debug("select_hibernate: selecting 'Hibernate performance'")
        self._session.window.child_window(
            title="Hibernate performance",
            auto_id=_AID_ASSESSMENT["hibernate"],
            control_type="ListItem",
        ).select()
        logger.debug("select_hibernate: clicking Run button")
        self._session.window.child_window(
            title="Run", auto_id=_AID_QUICKRUN_RUN_BTN, control_type="Button"
        ).click()
        logger.debug("select_hibernate: Run clicked")

    def select_bpfs_configured_job(self, num_iters: int = 1, auto_boot: bool = True) -> None:
        """Select BPFS via Run Individual Assessments, configure it, set job Overview, then click Run.

        UI steps performed:
            1. Click 'Run Individual Assessments' in the left panel.
            2. Select 'Boot performance (Fast Startup)' and click Configure.
            3. In the Configure job page — select the BPFS card on the left:
               - Uncheck 'Use recommended settings'
               - Set 'Number of Iterations' to *num_iters*
               - Ensure 'Use wake timers to automate boot' matches *auto_boot*
            4. Click 'Overview' in the left panel:
               - Ensure 'Stop this job if an error occurs' is checked
            5. Click 'Run' to submit the job.
        """
        logger.debug("select_bpfs_configured_job: num_iters=%d auto_boot=%s", num_iters, auto_boot)
        self._open_quickrun_panel()

        # Double-click BPFS in the Quick Run list to enter the Configure Job page.
        # WAC shows "Double-click an assessment from the list to continue." — this is
        # the reliable cross-build way to open the Configure page without needing to
        # locate the separate "Configure" button (whose control_type/auto_id differs
        # between build 22621 and 26100).
        logger.debug("select_bpfs_configured_job: double-clicking 'Boot performance (Fast Startup)' to open Configure page")
        ctrl = self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            control_type="ListItem",
        )
        ctrl.double_click_input()
        logger.debug("select_bpfs_configured_job: waiting for Configure Job page to load")
        time.sleep(2)

        # In the Configure Job left panel, click the BPFS assessment card to show settings.
        logger.debug("select_bpfs_configured_job: clicking BPFS card in Configure Job left panel")
        self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            control_type="ListItem",
        ).click_input()
        time.sleep(1)

        # Uncheck "Use recommended settings" (if currently checked)
        use_recommended = self._session.window.child_window(
            title="Use recommended settings",
            control_type="CheckBox",
        )
        state_rec = use_recommended.get_toggle_state()
        logger.debug("select_bpfs_configured_job: 'Use recommended settings' toggle_state=%d", state_rec)
        if state_rec == 1:
            logger.debug("select_bpfs_configured_job: unchecking 'Use recommended settings'")
            use_recommended.click_input()
        # Wait for the settings pane to become editable after unchecking recommended
        time.sleep(1)

        # Set Number of Iterations.
        # WAC's Edit control does not support IValueProvider.SetValue() (COMError
        # -2146233079), so we focus the field and use keyboard input instead.

        logger.debug("select_bpfs_configured_job: setting Iterations = %d via keyboard", num_iters)
        iter_ctrl = self._session.window.child_window(
            auto_id="AID_Parameter_Value_Iterations",
            control_type="Edit",
        )
        iter_ctrl.click_input()
        keyboard.send_keys("^a")    # select all existing text
        keyboard.send_keys(str(num_iters))
        time.sleep(0.3)
        actual_val = iter_ctrl.get_value()
        logger.debug("select_bpfs_configured_job: Iterations entered — field value readback='%s' (expected=%d)", actual_val, num_iters)

        # Set "Use wake timers to automate boot" to match auto_boot
        wake_timer = self._session.window.child_window(
            title="Use wake timers to automate boot (if supported)",
            control_type="CheckBox",
        )
        state_wt = wake_timer.get_toggle_state()
        logger.debug("select_bpfs_configured_job: wake_timer toggle_state=%d (want auto_boot=%s)", state_wt, auto_boot)
        if auto_boot and state_wt == 0:
            logger.debug("select_bpfs_configured_job: checking wake timers")
            wake_timer.click_input()
        elif not auto_boot and state_wt == 1:
            logger.debug("select_bpfs_configured_job: unchecking wake timers")
            wake_timer.click_input()

        # Click Overview in the left panel to reach job-level settings
        self._configure_job_overview_stop_on_error()

        # Click Run to submit
        logger.debug("select_bpfs_configured_job: clicking Run button (JobView)")
        self._session.window.child_window(
            title="Run", auto_id=_AID_JOBVIEW_RUN_BTN, control_type="Button"
        ).click()
        logger.debug("select_bpfs_configured_job: Run clicked")

    def _configure_job_overview_stop_on_error(self) -> None:
        """Click 'Overview' in the Configure Job left panel and ensure
        'Stop this job if an error occurs' is checked."""
        logger.debug("_configure_job_overview: clicking 'Overview' in left panel")
        self._session.window.child_window(
            title="Overview",
            control_type="ListItem",
        ).select()
        time.sleep(0.5)
        stop_cb = self._session.window.child_window(
            title="Stop this job if an error occurs",
            control_type="CheckBox",
        )
        state = stop_cb.get_toggle_state()
        logger.debug("_configure_job_overview: 'Stop this job if an error occurs' toggle_state=%d", state)
        if state == 0:
            logger.debug("_configure_job_overview: checking 'Stop this job if an error occurs'")
            stop_cb.click_input()

    def save_custom_job(self, name: str) -> None:
        """Fill in the 'Save Custom Job' dialog that appears after clicking Run
        in the Configure Job page, then confirm with OK.

        Args:
            name: The job name to enter (replaces the default 'New job N' text).
        """
        logger.debug("save_custom_job: waiting for Save Custom Job dialog")
        time.sleep(1)
        ctrl = self._session.window.child_window(
            auto_id=_AID_NAME_TEXTBOX,
            control_type="Edit",
        )
        logger.debug("save_custom_job: entering job name '%s'", name)
        ctrl.set_edit_text(name)
        logger.debug("save_custom_job: clicking OK")
        self._session.window.child_window(
            title="OK", control_type="Button"
        ).click()
        logger.debug("save_custom_job: dialog confirmed")
        time.sleep(1)

    # ------------------------------------------------------------------
    # Job name dialog (appears after Run is clicked in some assessments)
    # ------------------------------------------------------------------

    def set_job_name(self, name: str) -> None:
        """Enter the job name in the 'New job' dialog and confirm."""
        ctrl = self._session.window.child_window(
            title_re="New job", auto_id=_AID_NAME_TEXTBOX, control_type="Edit"
        )
        ctrl.set_edit_text(name)
        self._session.window["OK"].click()

    # ------------------------------------------------------------------
    # Start test
    # ------------------------------------------------------------------

    def click_start(self) -> None:
        """Click the Start button in the Assessment Launcher dialog."""
        logger.debug("click_start: clicking Start button in Assessment Launcher")
        self._session.window.child_window(
            title="Start", control_type="Button"
        ).click()
        logger.debug("click_start: Start clicked")

    def connect_launcher(self) -> None:
        """Connect to the Assessment Launcher window (appears after Run)."""
        logger.debug("connect_launcher: waiting for Assessment Launcher window (title_re='%s')", _LAUNCHER_TITLE_RE)
        try:
            app = Application(backend="uia").connect(
                title_re=_LAUNCHER_TITLE_RE, timeout=20
            )
            self._session.app = app
            self._session.window = app.window(title_re=_LAUNCHER_TITLE_RE)
            logger.debug("connect_launcher: connected to Assessment Launcher")
        except Exception as exc:
            raise ADKUIError(f"Failed to connect to Assessment Launcher: {exc}") from exc

    # ------------------------------------------------------------------
    # Result window helpers
    # ------------------------------------------------------------------

    def read_job_info(self, log_path: str) -> None:
        """Copy job details to clipboard and write JobInfo.log.

        Raises ADKUIError if the clipboard content indicates a warning/error.
        """
        logger.debug("read_job_info: clicking 'Copy details' to capture job info")
        pyperclip.copy("")
        self._session.window.child_window(
            title="Copy details", control_type="Button"
        ).click()
        content = pyperclip.waitForPaste()
        job_info_path = os.path.join(log_path, "JobInfo.log")
        logger.debug("read_job_info: writing %d chars to %s", len(content), job_info_path)
        with open(job_info_path, "w") as fp:
            fp.write(content)
        time.sleep(2)
        with open(job_info_path) as fp:
            for line in fp:
                if "Warning" in line:
                    # Tolerated warnings
                    if any(ok in line for ok in [
                        "[Warning] Windows is not genuine",
                        "[Warning] Conflicting application running",
                        "[Warning] Wireless networking is not enabled",
                    ]):
                        logger.debug("read_job_info: tolerated warning — %s", line.strip())
                        continue
                    raise ADKUIError(f"ADK warning: {line.strip()}")
                if "Error" in line:
                    raise ADKUIError(f"ADK error: {line.strip()}")
        logger.debug("read_job_info: job info validated, no blocking warnings/errors")
        pyperclip.copy("")

    def reconnect_wac_after_reboot(self) -> None:
        """Wait for WAC to reappear after a reboot, then bring it to focus."""
        logger.info(f"Waiting for {_WAC_TITLE} after reboot")
        while True:
            handles = findwindows.find_windows(title=_WAC_TITLE)
            if handles:
                logger.debug("reconnect_wac_after_reboot: WAC window found (handle=%s), connecting", handles[0])
                app = Application("uia").connect(handle=handles[0])
                self._session.app = app
                wnd = app.window(title=_WAC_TITLE)
                self._session.window = wnd
                wnd.maximize()
                wnd.set_focus()
                keyboard.send_keys("{PGDN}")
                logger.debug("reconnect_wac_after_reboot: WAC reconnected and focused")
                break
            logger.debug("reconnect_wac_after_reboot: WAC not yet visible, retrying in 10s")
            time.sleep(10)

    def read_view_results(
        self,
        timeout: int = 7200,
        debug_enumerate: bool = False,
    ) -> WACRunResult:
        """Wait for WAC to start, then wait for View Results page.

        After a BPFS-triggered reboot, pytest may start before WAC has
        relaunched its window.  This method retries the connect() call
        for the full *timeout* period so the assessment has time to finish.

        Args:
            timeout:         Max seconds to wait for WAC + View Results
                             (default 7200 = 2 hours).
            debug_enumerate: Set True to log all UI element IDs once the
                             View Results page appears (auto_id discovery).

        Returns:
            WACRunResult with errors, warnings, result_path, etc.

        Raises:
            ADKTimeoutError: WAC did not appear within *timeout* seconds.
        """
        _connect_poll = 10   # seconds between connect retries
        deadline = time.monotonic() + timeout

        # Phase 1: wait for WAC window to be available
        while True:
            try:
                if self._session.app is None or self._session.window is None:
                    self.connect()
                break   # connected
            except Exception as exc:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ADKTimeoutError(
                        f"WAC did not start within {timeout}s: {exc}"
                    ) from exc
                logger.info(
                    "[ViewResults] WAC not available yet (%s) — "
                    "retrying in %ds (remaining=%.0fs)",
                    type(exc).__name__, _connect_poll, remaining,
                )
                # Reset session so connect() tries a fresh attach next time
                self._session.app = None
                self._session.window = None
                time.sleep(_connect_poll)

        # Phase 2: wait for View Results page (assessment may still be running)
        remaining_timeout = max(int(deadline - time.monotonic()), 1)
        return wait_for_view_results(
            self._session.window,
            timeout=remaining_timeout,
            debug_enumerate=debug_enumerate,
        )

    def take_screenshot(self, log_path: str, result_dir_name: str) -> None:
        """Capture a full-screen screenshot and save it to log_path."""
        logger.debug("take_screenshot: connecting to WAC for screenshot")
        self.connect()
        self._session.window.maximize()
        self._session.window.set_focus()
        time.sleep(1)
        self._session.window.set_focus()
        screen = pyautogui.screenshot()
        dest = os.path.join(log_path, f"Finished_{result_dir_name}.png")
        screen.save(dest)
        logger.info(f"Screenshot saved: {dest}")

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    def _kill_process(self, process_name: str) -> None:
        """Terminate all processes matching *process_name* (case-insensitive)."""
        for proc in psutil.process_iter():
            try:
                if proc.name().lower() == process_name.lower():
                    proc.kill()
                    logger.info(f"Killed process: {process_name}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
