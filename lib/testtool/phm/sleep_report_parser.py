"""
PHM Sleep Study Report Parser  backward-compatible re-export shim

The canonical implementation has moved to
``lib.testtool.sleepstudy.sleep_report_parser``.
This module re-exports all public names so existing imports continue to work
without modification.

.. deprecated::
    Import directly from :mod:`lib.testtool.sleepstudy.sleep_report_parser`
    or from :mod:`lib.testtool.sleepstudy` instead.
"""
# ---------------------------------------------------------------------------
# Re-export shim  do NOT put any logic here.
# ---------------------------------------------------------------------------
from lib.testtool.sleepstudy.sleep_report_parser import (  # noqa: F401
    SleepReportParser,
    SleepSession,
    SESSION_TYPE_SLEEP,
    _TICKS_PER_SECOND,
)
