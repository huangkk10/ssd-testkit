"""
Windows ADK Controller

High-level orchestrator for Windows Assessment Console (WAC) test runs.
Inherits threading.Thread so callers can execute assessments asynchronously.

Install / uninstall is handled externally via ChocoManager:
    from lib.testtool.choco_manager import ChocoManager
    ChocoManager().install('windows-adk')

Usage example:
    from lib.testtool.windows_adk import ADKController

    ctrl = ADKController()
    ctrl.set_assessment("bpfs")
    ctrl.start()
    ctrl.join(timeout=600)
    ok, msg = ctrl.get_result()
"""

import asyncio
import os
import shutil
import subprocess
import threading
import time
import traceback
from pathlib import Path
from typing import Optional, Tuple

from lib.logger import get_module_logger
from .config import DEFAULT_CONFIG, WAC_EXE, get_build_number, merge_config
from .exceptions import ADKError, ADKResultError, ADKTimeoutError
from .result_parser import (
    check_result_bios_post_time,
    check_result_bpfs,
    check_result_hiberfile_read,
    check_result_standby,
    dump_result_json,
    parse_axelog,
    read_result_xml,
    save_result,
)
from .ui_runner import UIRunner
from .version_adapter import VersionAdapter

logger = get_module_logger(__name__)

# Assessment names map to (test_item_tag, ui_runner_method_name)
_ASSESSMENTS = {
    "bpfs":           ("boot_performance_fast_startup",  "select_bpfs"),
    "bpfb":           ("boot_performance_full_boot",     "select_bpfb"),
    "standby":        ("standby_performance",            "select_standby"),
    "modern_standby": ("standby_performance",            "select_modern_standby"),
    "hibernate":      ("hibernate_performance",          "select_hibernate"),
}


class ADKController(threading.Thread):
    """WAC test controller.

    Args:
        config: Optional dict to override DEFAULT_CONFIG keys.
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(daemon=True)
        self._config = merge_config(config or {})
        self._build = get_build_number()
        self._adapter = VersionAdapter(self._build)
        self._ui = UIRunner()

        # Runtime state
        self._assessment_name: str = ""
        self._assessment_kwargs: dict = {}
        self._result: Tuple[bool, str] = (False, "Not run yet")
        self._result_dir_name: str = ""
        self._lock = threading.Lock()

        logger.info(
            f"ADKController init: build={self._build} "
            f"({self._adapter.os_name()}), "
            f"log_path={self._config['log_path']}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_assessment(self, name: str, **kwargs) -> None:
        """Set the assessment to run.

        Args:
            name: One of 'bpfs', 'bpfb', 'standby', 'modern_standby', 'hibernate'.
            **kwargs: Extra options forwarded to the UI runner
                      (e.g. num_iters=5, auto_boot=False for bpfs_num_iters).
        """
        _extra = ["bpfs_num_iters", "bpfs_configured"]
        if name not in _ASSESSMENTS and name not in _extra:
            raise ADKError(
                f"Unknown assessment: '{name}'. "
                f"Valid options: {sorted(list(_ASSESSMENTS.keys()) + _extra)}"
            )
        self._assessment_name = name
        self._assessment_kwargs = kwargs

    def get_result(self) -> Tuple[bool, str]:
        """Return the (passed, message) tuple from the last run."""
        with self._lock:
            return self._result

    def get_power_state(self) -> str:
        """Detect S3 / Modern Standby (CS) / Unknown via powercfg -a."""
        try:
            lines = subprocess.check_output(["powercfg", "-a"]).splitlines()
        except Exception as exc:
            logger.error(f"powercfg failed: {exc}")
            return "Unknown"
        for line in lines:
            if b"Standby (S0 Low Power Idle) Network Connected" in line:
                logger.info("Power state: CS")
                return "CS"
            if b"Standby (S3)" in line:
                logger.info("Power state: S3")
                return "S3"
        logger.error("Power state: Unknown")
        return "Unknown"

    def cleanup_dirs(self) -> None:
        """Remove and recreate WAC result, job, and test directories."""
        for directory in (
            self._adapter.get_result_dir(),
            self._adapter.get_job_dir(),
            self._adapter.get_test_dir(),
        ):
            if os.path.exists(directory):
                shutil.rmtree(directory)
            Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info("WAC directories cleaned")

    def save_result(self) -> None:
        """Copy assessment result to log_path and dump JSON."""
        result_dir = self._adapter.get_result_dir()
        save_result(result_dir, self._config["log_path"], self._result_dir_name)
        results = read_result_xml(result_dir, self._adapter.username, self._result_dir_name)
        dump_result_json(results, self._config["log_path"], self._result_dir_name)

    def take_screenshot(self) -> None:
        """Capture a screenshot of the WAC result window."""
        self._ui.take_screenshot(self._config["log_path"], self._result_dir_name)

    def reconnect(self) -> None:
        """Reconnect to WAC after a reboot (call from the reconnect test flow)."""
        self._ui.reconnect_wac_after_reboot()

    # ------------------------------------------------------------------
    # threading.Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute the configured assessment synchronously on this thread."""
        if not self._assessment_name:
            raise ADKError("No assessment set — call set_assessment() first")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._run_assessment())
            with self._lock:
                self._result = result
        except Exception as exc:
            logger.error(traceback.format_exc())
            with self._lock:
                self._result = (False, str(exc))
        finally:
            loop.close()

    # ------------------------------------------------------------------
    # Internal assessment flows
    # ------------------------------------------------------------------

    async def _run_assessment(self) -> Tuple[bool, str]:
        """Dispatch to the correct assessment flow."""
        name = self._assessment_name
        log_path = self._config["log_path"]
        os.makedirs(log_path, exist_ok=True)

        self.cleanup_dirs()
        self._ui.open(WAC_EXE)

        if name == "bpfs":
            self._ui.select_bpfs()
            self._ui.connect_launcher()
            self._ui.read_job_info(log_path)
            await self._ui_click_start_async()
            ok, msg = await self._scan_finished()
            if not ok:
                return False, msg
            ok, msg = self._check_finish_result()
            self.save_result()
            self.take_screenshot()
            if ok and self._config["check_result_spec"]:
                ok, msg = self._check_spec_bpfs()
            self._ui.close()
            return ok, msg

        if name == "bpfs_num_iters":
            num_iters = self._assessment_kwargs.get("num_iters", 3)
            auto_boot = self._assessment_kwargs.get("auto_boot", True)
            self._ui.select_bpfs_num_iters(num_iters, auto_boot)
            self._ui.connect_launcher()
            self._ui.read_job_info(log_path)
            await self._ui_click_start_async()
            ok, msg = await self._scan_finished()
            if not ok:
                return False, msg
            ok, msg = self._check_finish_result()
            self.save_result()
            self.take_screenshot()
            self._ui.close()
            return ok, msg

        if name == "bpfs_configured":
            num_iters = self._assessment_kwargs.get("num_iters", 1)
            auto_boot = self._assessment_kwargs.get("auto_boot", True)
            job_name  = self._assessment_kwargs.get("job_name", "BPFS_Test")
            self._ui.select_bpfs_configured_job(num_iters, auto_boot)
            self._ui.save_custom_job(job_name)
            self._ui.connect_launcher()
            self._ui.read_job_info(log_path)
            await self._ui_click_start_async()
            ok, msg = await self._scan_finished()
            if not ok:
                return False, msg
            ok, msg = self._check_finish_result()
            self.save_result()
            self.take_screenshot()
            if ok and self._config["check_result_spec"]:
                ok, msg = self._check_spec_bpfs()
            self._ui.close()
            return ok, msg

        if name == "bpfb":
            self._ui.select_bpfb()
            self._ui.connect_launcher()
            self._ui.read_job_info(log_path)
            await self._ui_click_start_async()
            ok, msg = await self._scan_finished()
            if not ok:
                return False, msg
            ok, msg = self._check_finish_result()
            self.save_result()
            self.take_screenshot()
            self._ui.close()
            return ok, msg

        if name in ("standby", "modern_standby"):
            getattr(self._ui, _ASSESSMENTS[name][1])()
            self._ui.connect_launcher()
            self._ui.read_job_info(log_path)
            await self._ui_click_start_async()
            ok, msg = await self._scan_finished()
            if not ok:
                return False, msg
            await self._scan_title_after_reboot()
            ok, msg = self._check_finish_result()
            self.save_result()
            self.take_screenshot()
            if name == "standby" and ok and self._config["check_result_spec"]:
                ok, msg = self._check_spec_standby()
            self._ui.close()
            return ok, msg

        if name == "hibernate":
            self._ui.select_hibernate()
            self._ui.connect_launcher()
            self._ui.read_job_info(log_path)
            await self._ui_click_start_async()
            ok, msg = await self._scan_finished()
            if not ok:
                return False, msg
            await self._scan_title_after_reboot()
            ok, msg = self._check_finish_result()
            self.save_result()
            self.take_screenshot()
            self._ui.close()
            return ok, msg

        raise ADKError(f"Unhandled assessment: {name}")

    async def _ui_click_start_async(self) -> None:
        self._ui.click_start()
        await asyncio.sleep(1)

    async def _scan_finished(self) -> Tuple[bool, str]:
        """Poll the in-flight test dir until WAC finalises the result directory."""
        test_dir = self._adapter.get_test_dir()
        result_dir = self._adapter.get_result_dir()
        max_iter = self._config["scan_timeout_iterations"]
        interval = self._config["scan_interval_seconds"]

        # Wait for the in-flight directory to appear
        for i in range(max_iter):
            items = os.listdir(test_dir) if os.path.isdir(test_dir) else []
            if items:
                self._result_dir_name = items[0]
                break
            await asyncio.sleep(1)
        else:
            return False, "Timed out waiting for test result directory"

        logger.info(f"Result dir name: {self._result_dir_name}")

        # Now wait for WAC to move it to the final result dir
        final_path = os.path.join(result_dir, self._result_dir_name)
        axelog_path = os.path.join(test_dir, self._result_dir_name, "AxeLog.txt")
        while True:
            if os.path.isdir(final_path):
                logger.info("Assessment finished")
                return True, "Finished"
            if os.path.exists(axelog_path):
                msg = f"Test error: AxeLog.txt found at {axelog_path}"
                logger.error(msg)
                return False, msg
            logger.info("Waiting for assessment to finish…")
            await asyncio.sleep(interval)

    async def _scan_title_after_reboot(self) -> None:
        """Wait for WAC window to reappear after a reboot."""
        self._ui.reconnect_wac_after_reboot()

    def _check_finish_result(self) -> Tuple[bool, str]:
        """Read AxeLog.txt from the final result directory."""
        result_dir = self._adapter.get_result_dir()
        axelog = os.path.join(result_dir, self._result_dir_name, "AxeLog.txt")
        return parse_axelog(axelog)

    def _check_spec_bpfs(self) -> Tuple[bool, str]:
        result_dir = self._adapter.get_result_dir()
        results = read_result_xml(result_dir, self._adapter.username, self._result_dir_name)
        return check_result_bpfs(results, self._config["thresholds"])

    def _check_spec_standby(self) -> Tuple[bool, str]:
        result_dir = self._adapter.get_result_dir()
        results = read_result_xml(result_dir, self._adapter.username, self._result_dir_name)
        return check_result_standby(results, self._config["thresholds"])
