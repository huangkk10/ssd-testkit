"""
SleepStudy Testtool Package

Wraps Windows ``powercfg /sleepstudy`` — generates the HTML report and
provides a structured parser for the embedded sleep-session data.

Main Components
---------------
- :class:`~.controller.SleepStudyController`
    Threading controller that runs ``powercfg /sleepstudy /output <path>``
    and exposes the resulting HTML via :meth:`~.controller.SleepStudyController.get_parser`.
- :class:`~.sleep_report_parser.SleepReportParser`
    Parses the HTML report; returns :class:`~.sleep_report_parser.SleepSession` objects.
- :class:`~.sleep_report_parser.SleepSession`
    Data-class for a single sleep session (id, times, SW/HW DRIPS %).
- :class:`~.config.SleepStudyConfig`
    Configuration container.
- Custom exceptions — see :mod:`.exceptions`.

Quick-start
-----------
Generate a fresh report and parse it::

    from lib.testtool.sleepstudy import SleepStudyController

    ctrl = SleepStudyController(output_path="C:/tmp/report.html", timeout=60)
    ctrl.start()
    ctrl.join()

    if ctrl.status:
        parser = ctrl.get_parser()
        sessions = parser.get_sleep_sessions(
            start_dt="2026-03-04T00:00:00",
            end_dt="2026-03-04T23:59:59",
        )
        for s in sessions:
            print(s.session_id, s.duration_hms, s.sw_pct, s.hw_pct)
    else:
        print(f"Failed: {ctrl.error_message}")

Parse an already-existing report::

    from lib.testtool.sleepstudy import SleepReportParser

    parser = SleepReportParser(r"C:\\tmp\\sleepstudy-report.html")
    sessions = parser.get_sleep_sessions()
    for s in sessions:
        print(s.session_id, s.sw_pct)
"""

from .controller import SleepStudyController
from .config import SleepStudyConfig
from .sleep_report_parser import SleepReportParser, SleepSession
from .exceptions import (
    SleepStudyError,
    SleepStudyConfigError,
    SleepStudyTimeoutError,
    SleepStudyProcessError,
    SleepStudyLogParseError,
    SleepStudyTestFailedError,
)

__version__ = "1.0.0"

__all__ = [
    # Controller
    "SleepStudyController",
    # Configuration
    "SleepStudyConfig",
    # Report parsing
    "SleepReportParser",
    "SleepSession",
    # Exceptions
    "SleepStudyError",
    "SleepStudyConfigError",
    "SleepStudyTimeoutError",
    "SleepStudyProcessError",
    "SleepStudyLogParseError",
    "SleepStudyTestFailedError",
]
