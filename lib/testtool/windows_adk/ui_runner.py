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
from .exceptions import ADKUIError, ADKProcessError

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
        try:
            self._session.app = Application(backend="uia").start(wac_exe)
            self._session.window = self._session.app.window(title_re=_WAC_TITLE)
            time.sleep(2)
            while True:
                if self._session.window.exists():
                    self._session.window.maximize()
                    break
                time.sleep(2)
            logger.info("WAC opened successfully")
        except Exception as exc:
            raise ADKUIError(f"Failed to open WAC: {exc}") from exc

    def close(self) -> None:
        """Kill axe.exe (assessment engine) and the WAC process."""
        self._kill_process("axe.exe")
        try:
            if self._session.app:
                self._session.app.kill()
        except Exception as exc:
            logger.error(f"Error closing WAC: {exc}")

    def connect(self) -> None:
        """Reconnect to an already-running WAC window (e.g. after reboot)."""
        try:
            self._session.app = Application(backend="uia").connect(title=_WAC_TITLE)
            self._session.window = self._session.app.window(title=_WAC_TITLE)
        except Exception as exc:
            raise ADKUIError(f"Failed to connect to WAC: {exc}") from exc

    # ------------------------------------------------------------------
    # Assessment selection helpers (Quick Run panel)
    # ------------------------------------------------------------------

    def _open_quickrun_panel(self) -> None:
        """Click 'Run Individual Assessments' to open the Quick Run list."""
        ctrl = self._session.window.child_window(
            title="Run Individual Assessments",
            auto_id=_AID_QUICKRUN_PANEL,
            control_type="ListItem",
        )
        ctrl.select()
        time.sleep(2)

    def select_bpfs(self) -> None:
        """Select Boot Performance (Fast Startup) and click Run."""
        self._open_quickrun_panel()
        ctrl = self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            auto_id=_AID_ASSESSMENT["bpfs"],
            control_type="ListItem",
        )
        ctrl.select()
        self._session.window.child_window(
            title="Run", auto_id=_AID_QUICKRUN_RUN_BTN, control_type="Button"
        ).click()

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
        self._open_quickrun_panel()
        ctrl = self._session.window.child_window(
            title="Boot performance (Full Boot)",
            auto_id=_AID_ASSESSMENT["bpfb"],
            control_type="ListItem",
        )
        ctrl.select()
        self._session.window.child_window(
            title="Run", auto_id=_AID_QUICKRUN_RUN_BTN, control_type="Button"
        ).click()

    def select_standby(self) -> None:
        """Select Standby Performance and click Run."""
        self._open_quickrun_panel()
        # Scroll down to reveal Standby from BPFS item
        focus_ctrl = self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            auto_id=_AID_ASSESSMENT["bpfs"],
            control_type="ListItem",
        )
        focus_ctrl.select()
        focus_ctrl.set_focus()
        keyboard.send_keys("{PGDN}{PGDN}{PGDN}")
        self._session.window.child_window(
            title="Standby performance",
            auto_id=_AID_ASSESSMENT["standby"],
            control_type="ListItem",
        ).select()
        self._session.window.child_window(
            title="Run", auto_id=_AID_QUICKRUN_RUN_BTN, control_type="Button"
        ).click()

    def select_modern_standby(self) -> None:
        """Select Modern Standby Performance and click Run."""
        self._open_quickrun_panel()
        focus_ctrl = self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            auto_id=_AID_ASSESSMENT["bpfs"],
            control_type="ListItem",
        )
        focus_ctrl.select()
        focus_ctrl.set_focus()
        keyboard.send_keys("{PGDN}{PGDN}{PGDN}")
        self._session.window.child_window(
            title="Modern Standby Performance",
            auto_id=_AID_ASSESSMENT["modern_standby"],
            control_type="ListItem",
        ).select()
        self._session.window.child_window(
            title="Run", auto_id=_AID_QUICKRUN_RUN_BTN, control_type="Button"
        ).click()

    def select_hibernate(self) -> None:
        """Select Hibernate Performance and click Run."""
        self._open_quickrun_panel()
        focus_ctrl = self._session.window.child_window(
            auto_id=_AID_QUICKRUN_PANEL,
            control_type="ListItem",
        )
        focus_ctrl.set_focus()
        self._session.window.child_window(
            title="Hibernate performance",
            auto_id=_AID_ASSESSMENT["hibernate"],
            control_type="ListItem",
        ).select()
        self._session.window.child_window(
            title="Run", auto_id=_AID_QUICKRUN_RUN_BTN, control_type="Button"
        ).click()

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
        self._open_quickrun_panel()

        # Select BPFS in the Quick Run list
        ctrl = self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            auto_id=_AID_ASSESSMENT["bpfs"],
            control_type="ListItem",
        )
        ctrl.select()

        # Click "Configure" hyperlink → opens the Configure Job tab
        self._session.window.child_window(
            title="Configure",
            auto_id="AID_QuickRun_ConfigureAndRun",
            control_type="Hyperlink",
        ).invoke()
        time.sleep(1)

        # In the Configure Job left panel, select the BPFS assessment card
        self._session.window.child_window(
            title="Boot performance (Fast Startup)",
            auto_id=_AID_ASSESSMENT["bpfs"],
            control_type="ListItem",
        ).select()
        time.sleep(0.5)

        # Uncheck "Use recommended settings" (if currently checked)
        use_recommended = self._session.window.child_window(
            title="Use recommended settings",
            auto_id="AID_AssessmentView_BenchmarkMode",
            control_type="CheckBox",
        )
        if use_recommended.get_toggle_state() == 1:
            use_recommended.click_input()

        # Set Number of Iterations
        iter_ctrl = self._session.window.child_window(
            auto_id="AID_Parameter_Value_Iterations",
            control_type="Edit",
        )
        iter_ctrl.set_edit_text(str(num_iters))

        # Set "Use wake timers to automate boot" to match auto_boot
        wake_timer = self._session.window.child_window(
            title="Use wake timers to automate boot (if supported)",
            auto_id="AID_Parameter_Value_waketimersupport",
            control_type="CheckBox",
        )
        state = wake_timer.get_toggle_state()
        if auto_boot and state == 0:
            wake_timer.click_input()
        elif not auto_boot and state == 1:
            wake_timer.click_input()

        # Click Overview in the left panel to reach job-level settings
        self._configure_job_overview_stop_on_error()

        # Click Run to submit
        self._session.window.child_window(
            title="Run", auto_id=_AID_JOBVIEW_RUN_BTN, control_type="Button"
        ).click()

    def _configure_job_overview_stop_on_error(self) -> None:
        """Click 'Overview' in the Configure Job left panel and ensure
        'Stop this job if an error occurs' is checked."""
        self._session.window.child_window(
            title="Overview",
            control_type="ListItem",
        ).select()
        time.sleep(0.5)
        stop_cb = self._session.window.child_window(
            title="Stop this job if an error occurs",
            control_type="CheckBox",
        )
        if stop_cb.get_toggle_state() == 0:
            stop_cb.click_input()

    def save_custom_job(self, name: str) -> None:
        """Fill in the 'Save Custom Job' dialog that appears after clicking Run
        in the Configure Job page, then confirm with OK.

        Args:
            name: The job name to enter (replaces the default 'New job N' text).
        """
        time.sleep(1)
        ctrl = self._session.window.child_window(
            auto_id=_AID_NAME_TEXTBOX,
            control_type="Edit",
        )
        ctrl.set_edit_text(name)
        self._session.window.child_window(
            title="OK", control_type="Button"
        ).click()
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
        self._session.window.child_window(
            title="Start", auto_id=_AID_START_BTN, control_type="Button"
        ).click()

    def connect_launcher(self) -> None:
        """Connect to the Assessment Launcher window (appears after Run)."""
        try:
            app = Application(backend="uia").connect(
                title_re=_LAUNCHER_TITLE_RE, timeout=20
            )
            self._session.app = app
            self._session.window = app.window(title_re=_LAUNCHER_TITLE_RE)
        except Exception as exc:
            raise ADKUIError(f"Failed to connect to Assessment Launcher: {exc}") from exc

    # ------------------------------------------------------------------
    # Result window helpers
    # ------------------------------------------------------------------

    def read_job_info(self, log_path: str) -> None:
        """Copy job details to clipboard and write JobInfo.log.

        Raises ADKUIError if the clipboard content indicates a warning/error.
        """
        pyperclip.copy("")
        self._session.window.child_window(
            title="Copy details", auto_id=_AID_COPY_DETAILS_BTN, control_type="Button"
        ).click()
        content = pyperclip.waitForPaste()
        job_info_path = os.path.join(log_path, "JobInfo.log")
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
                        continue
                    raise ADKUIError(f"ADK warning: {line.strip()}")
                if "Error" in line:
                    raise ADKUIError(f"ADK error: {line.strip()}")
        pyperclip.copy("")

    def reconnect_wac_after_reboot(self) -> None:
        """Wait for WAC to reappear after a reboot, then bring it to focus."""
        logger.info(f"Waiting for {_WAC_TITLE} after reboot")
        while True:
            handles = findwindows.find_windows(title=_WAC_TITLE)
            if handles:
                app = Application("uia").connect(handle=handles[0])
                self._session.app = app
                wnd = app.window(title=_WAC_TITLE)
                self._session.window = wnd
                wnd.maximize()
                wnd.set_focus()
                keyboard.send_keys("{PGDN}")
                break
            time.sleep(10)

    def take_screenshot(self, log_path: str, result_dir_name: str) -> None:
        """Capture a full-screen screenshot and save it to log_path."""
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
