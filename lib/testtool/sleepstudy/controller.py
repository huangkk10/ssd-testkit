"""
SleepStudy Controller

Threading-based controller that runs ``powercfg /sleepstudy /output <path>``
and exposes the resulting HTML report via :class:`SleepReportParser`.

Usage::

    from lib.testtool.sleepstudy import SleepStudyController

    ctrl = SleepStudyController(output_path="C:/tmp/report.html", timeout=60)
    ctrl.start()
    ctrl.join()

    if ctrl.status:
        parser = ctrl.get_parser()
        sessions = parser.get_sleep_sessions(start_dt="2026-03-04")
        for s in sessions:
            print(s.session_id, s.sw_pct)
    else:
        print(f"Failed: {ctrl.error_message}")
"""

import subprocess
import threading
from pathlib import Path
from typing import Optional

from lib.logger import get_module_logger
from .config import SleepStudyConfig, merge_config
from .exceptions import (
    SleepStudyConfigError,
    SleepStudyProcessError,
    SleepStudyTimeoutError,
)
from .sleep_report_parser import SleepReportParser

logger = get_module_logger(__name__)


class SleepStudyController(threading.Thread):
    """
    Controller for generating a Windows Sleep Study HTML report.

    Runs ``powercfg /sleepstudy /output <output_path>`` inside a daemon
    thread.  After :meth:`join` returns, check :attr:`status` and call
    :meth:`get_parser` to analyse the results.

    Args:
        output_path: Destination path for the HTML report.
                     Defaults to ``"sleepstudy-report.html"`` in the
                     current working directory.
        timeout:     Maximum seconds to wait for ``powercfg`` to finish.
                     Defaults to ``60``.
        **kwargs:    Additional keys forwarded to :func:`~.config.merge_config`
                     (currently no extra keys are defined).

    Attributes:
        status (bool | None): ``None`` before :meth:`start`, ``True`` on
            success, ``False`` on failure.
        error_message (str | None): Human-readable failure reason or ``None``.

    Example::

        ctrl = SleepStudyController(output_path="./report.html", timeout=30)
        ctrl.start()
        ctrl.join()
        assert ctrl.status
    """

    def __init__(
        self,
        output_path: str = "sleepstudy-report.html",
        timeout: int = 60,
        **kwargs,
    ) -> None:
        super().__init__(daemon=True)
        config_overrides = {"output_path": output_path, "timeout": timeout}
        config_overrides.update(kwargs)
        config = merge_config(config_overrides)

        self._output_path = Path(config["output_path"]).resolve()
        self._timeout = config["timeout"]

        self.status: Optional[bool] = None
        self.error_message: Optional[str] = None

    # ------------------------------------------------------------------
    # threading.Thread interface
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute ``powercfg /sleepstudy /output <path>`` synchronously."""
        logger.info(
            "SleepStudyController: generating report → %s", self._output_path
        )
        # Ensure parent directory exists
        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "powercfg",
            "/sleepstudy",
            "/output",
            str(self._output_path),
        ]
        logger.debug("Running: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self.status = False
            self.error_message = (
                f"powercfg /sleepstudy timed out after {self._timeout}s"
            )
            logger.error(self.error_message)
            return
        except FileNotFoundError as exc:
            self.status = False
            self.error_message = f"powercfg.exe not found: {exc}"
            logger.error(self.error_message)
            return
        except Exception as exc:
            self.status = False
            self.error_message = f"Unexpected error running powercfg: {exc}"
            logger.error(self.error_message)
            return

        if result.returncode != 0:
            self.status = False
            self.error_message = (
                f"powercfg /sleepstudy exited with code {result.returncode}. "
                f"stderr: {result.stderr.strip()}"
            )
            logger.error(self.error_message)
            return

        if not self._output_path.exists():
            self.status = False
            self.error_message = (
                f"Report not produced at expected path: {self._output_path}"
            )
            logger.error(self.error_message)
            return

        self.status = True
        logger.info("SleepStudyController: report ready at %s", self._output_path)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_parser(self) -> SleepReportParser:
        """
        Return a :class:`~.sleep_report_parser.SleepReportParser` for the
        generated HTML report.

        Should only be called after the thread has finished (i.e. after
        :meth:`join`) and :attr:`status` is ``True``.

        Raises:
            :class:`~.exceptions.SleepStudyProcessError`: if the report was
                not produced (controller not run yet, or run failed).
        """
        if not self._output_path.exists():
            raise SleepStudyProcessError(
                f"Report HTML not found at {self._output_path}. "
                "Run the controller first and ensure status is True."
            )
        return SleepReportParser(str(self._output_path))

    @property
    def output_path(self) -> Path:
        """Resolved path to the HTML report file."""
        return self._output_path
