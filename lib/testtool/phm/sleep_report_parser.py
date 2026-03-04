"""
PHM Sleep Study Report Parser

Parses the HTML report produced by Windows ``powercfg /sleepstudy``.

The report embeds a ``LocalSprData`` JSON object inside a ``<script>`` tag.
This module extracts that JSON, filters sessions by type (Sleep = Type 2) and
an optional date/time range, and returns structured
:class:`SleepSession` objects.

Playwright is used to load and evaluate the HTML page so that all
inline JavaScript is executed before the DOM is queried.  The JSON
payload is read directly from the script tag without browser rendering
since the data we need lives entirely in the embedded JSON.

Example::

    from lib.testtool.phm.sleep_report_parser import SleepReportParser

    parser = SleepReportParser(r"C:\\tmp\\sleepstudy-report.html")
    sessions = parser.get_sleep_sessions(
        start_dt="2026-03-04T00:00:00",
        end_dt="2026-03-04T23:59:59",
    )
    for s in sessions:
        print(s.session_id, s.duration_seconds, s.sw_pct, s.hw_pct)
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Union

from .exceptions import PHMLogParseError
from lib.logger import get_module_logger

logger = get_module_logger(__name__)

# ---------------------------------------------------------------------------
# Session type constants (matches SESSION_TYPE_NAMES in the HTML JS)
# ---------------------------------------------------------------------------
SESSION_TYPE_SLEEP = 2  # "Sleep"

# Duration unit in the JSON: 100-nanosecond ticks (Windows FILETIME)
_TICKS_PER_SECOND = 1e7


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SleepSession:
    """
    A single Sleep session extracted from a Windows Sleep Study HTML report.

    Attributes:
        session_id:       Unique session identifier from the report.
        entry_time_local: Session start time (local clock, timezone-naive
                          ``datetime`` parsed from ``EntryTimestampLocal``).
        exit_time_local:  Session end time (local clock, timezone-naive
                          ``datetime`` parsed from ``ExitTimestampLocal``).
        duration_seconds: Sleep duration in seconds (float).
        sw_pct:           Software DRIPS percentage (``SW:`` column).
                          ``None`` if the report does not provide this value.
        hw_pct:           Hardware DRIPS percentage (``HW:`` column).
                          ``None`` if the report does not provide this value.
        on_ac:            ``True`` if the machine was on AC power during this
                          session, ``False`` for battery drain.
        raw:              The raw session dict from the JSON payload.
    """

    session_id: int = 0
    entry_time_local: Optional[datetime] = None
    exit_time_local: Optional[datetime] = None
    duration_seconds: float = 0.0
    sw_pct: Optional[int] = None
    hw_pct: Optional[int] = None
    on_ac: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def duration_hms(self) -> str:
        """Return duration as ``H:MM:SS`` string (same as the HTML table)."""
        total = int(self.duration_seconds)
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class SleepReportParser:
    """
    Parse a Windows Sleep Study HTML report (``powercfg /sleepstudy``).

    The report embeds all session data as a ``LocalSprData`` JSON object
    inside a ``<script>`` block.  This parser:

    1. Reads the HTML file with Playwright (chromium headless) to resolve
       any encoding issues and validate the file is loadable.
    2. Extracts the ``LocalSprData`` JSON via a ``page.evaluate()`` call
       so the value is taken directly from the live JavaScript environment.
    3. Filters sessions to those with ``Type == 2`` (Sleep).
    4. Optionally narrows by a local-time date/time range.

    Args:
        html_path: Path to the ``sleepstudy-report.html`` file.

    Raises:
        :class:`~.exceptions.PHMLogParseError`: if the file does not exist,
            cannot be read, or does not contain the expected JSON payload.

    Example::

        parser = SleepReportParser("./tmp/sleepstudy-report.html")
        all_sleep = parser.get_sleep_sessions()
        filtered  = parser.get_sleep_sessions(
            start_dt="2026-03-04T10:00:00",
            end_dt="2026-03-04T23:59:59",
        )
    """

    def __init__(self, html_path: str) -> None:
        self.html_path = Path(html_path).resolve()
        if not self.html_path.exists():
            raise PHMLogParseError(f"Sleep study HTML not found: {self.html_path}")
        self._raw_data: Optional[dict] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_sleep_sessions(
        self,
        start_dt: Union[str, datetime, None] = None,
        end_dt: Union[str, datetime, None] = None,
    ) -> List[SleepSession]:
        """
        Return a list of :class:`SleepSession` objects from the report.

        Only ``Type == 2`` (Sleep) sessions are returned.  If *start_dt*
        and/or *end_dt* are provided the session's **entry time** (local
        clock) must fall within ``[start_dt, end_dt]`` (both inclusive).

        Both parameters accept either a :class:`datetime` object **or** an
        ISO-8601 string.  Using ``datetime`` directly is recommended when
        building the filter programmatically::

            from datetime import datetime
            parser.get_sleep_sessions(
                start_dt=datetime(2026, 3, 4, 11, 0),
                end_dt=datetime(2026, 3, 4, 11, 30),
            )

        String shortcuts are also accepted::

            parser.get_sleep_sessions(
                start_dt="2026-03-04T11:00",
                end_dt="2026-03-04T11:30",
            )
            # date-only end_dt is automatically treated as 23:59:59
            parser.get_sleep_sessions(start_dt="2026-03-04", end_dt="2026-03-04")

        Args:
            start_dt: Lower bound (inclusive) for session entry time.
                      ``datetime`` object, ISO-8601 string, or ``None``
                      (no lower bound).  Date-only strings resolve to
                      ``00:00:00``.
            end_dt:   Upper bound (inclusive) for session entry time.
                      ``datetime`` object, ISO-8601 string, or ``None``
                      (no upper bound).  Date-only strings resolve to
                      ``23:59:59`` so the full day is included.

        Returns:
            Ordered list of matching :class:`SleepSession` objects sorted by
            ``entry_time_local`` ascending.

        Raises:
            :class:`~.exceptions.PHMLogParseError`: on parse failure.
        """
        data = self._load_data()
        scenarios = data.get("ScenarioInstances", [])

        start = self._resolve_dt_arg(start_dt) if start_dt is not None else None
        end = self._resolve_end_dt_arg(end_dt) if end_dt is not None else None

        sessions: List[SleepSession] = []
        for raw_session in scenarios:
            if raw_session.get("Type") != SESSION_TYPE_SLEEP:
                continue
            session = self._build_session(raw_session)
            if start is not None and session.entry_time_local < start:
                continue
            if end is not None and session.entry_time_local > end:
                continue
            sessions.append(session)

        sessions.sort(key=lambda s: s.entry_time_local or datetime.min)
        logger.debug(
            "get_sleep_sessions: %d session(s) matched (start=%s end=%s)",
            len(sessions), start_dt, end_dt,
        )
        return sessions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_data(self) -> dict:
        """
        Load and cache the ``LocalSprData`` JSON from the HTML file.

        Extraction strategy (in order):

        1. **Regex** — fast, zero dependencies, works because ``LocalSprData``
           is a static JSON literal on a single line in the ``<script>`` block.
        2. **Playwright** — headless Chromium fallback used only when the regex
           fails (e.g. the JSON spans multiple lines in a future report version).
        """
        if self._raw_data is not None:
            return self._raw_data
        try:
            self._raw_data = self._extract_json_via_regex()
            logger.debug("LocalSprData extracted via regex (fast path)")
        except PHMLogParseError as regex_err:
            logger.debug(
                "Regex extraction failed (%s); retrying with Playwright", regex_err
            )
            self._raw_data = self._extract_json_via_playwright()
        return self._raw_data

    def _extract_json_via_playwright(self) -> dict:
        """
        Playwright (chromium headless) fallback: open the HTML file in a real
        browser and read ``LocalSprData`` from the live JavaScript environment
        via ``page.evaluate()``.

        This path is only taken when :meth:`_extract_json_via_regex` fails.
        Requires ``playwright install chromium``.

        Returns:
            The ``LocalSprData`` dict.

        Raises:
            :class:`~.exceptions.PHMLogParseError`: if Playwright fails or
                ``LocalSprData`` is not found in the page.
        """
        try:
            from playwright.sync_api import sync_playwright, Error as PlaywrightError
        except ImportError as exc:
            raise PHMLogParseError(
                "playwright package is required: pip install playwright && "
                "playwright install chromium"
            ) from exc

        file_url = self.html_path.as_uri()
        logger.debug("Loading sleep study HTML via Playwright: %s", file_url)

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(file_url, wait_until="domcontentloaded", timeout=30_000)
                # Evaluate the LocalSprData JS variable that is defined
                # inline in the HTML <script> block.
                data = page.evaluate("() => typeof LocalSprData !== 'undefined' ? LocalSprData : null")
                browser.close()
        except Exception as exc:
            raise PHMLogParseError(
                f"Playwright failed to load '{self.html_path}': {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise PHMLogParseError(
                f"LocalSprData is not a dict in '{self.html_path}'"
            )
        return data

    def _extract_json_via_regex(self) -> dict:
        """
        Primary parser: extract ``LocalSprData = {...}`` from raw HTML
        using a line-oriented regex match, then ``json.loads``.

        This is the fast path — no browser required.  ``LocalSprData`` is
        always emitted as a single (long) line in the ``<script>`` block by
        the Windows Sleep Study generator.

        Raises:
            :class:`~.exceptions.PHMLogParseError`: if the pattern is not found
                or the JSON is malformed.
        """
        html_text = self.html_path.read_text(encoding="utf-8")
        pattern = re.compile(r'var LocalSprData\s*=\s*(\{.+?\})\s*;', re.DOTALL)
        # The JSON is always on a single (very long) line so we can use a
        # line-oriented match first which is much faster.
        for line in html_text.splitlines():
            m = re.match(r'\s*var LocalSprData = (.+);$', line)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError as exc:
                    raise PHMLogParseError(
                        f"Failed to decode LocalSprData JSON: {exc}"
                    ) from exc
        # Try multiline fallback
        m = pattern.search(html_text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError as exc:
                raise PHMLogParseError(
                    f"Failed to decode LocalSprData JSON (multiline): {exc}"
                ) from exc
        raise PHMLogParseError(
            f"'LocalSprData' variable not found in '{self.html_path}'"
        )

    # ------------------------------------------------------------------
    # Session building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_session(raw: dict) -> SleepSession:
        """Convert a raw scenario dict to a :class:`SleepSession`."""
        dur_ticks = raw.get("Duration", 0) or 0
        dur_seconds = dur_ticks / _TICKS_PER_SECOND

        entry_local = SleepReportParser._parse_timestamp(
            raw.get("EntryTimestampLocal")
        )
        exit_local = SleepReportParser._parse_timestamp(
            raw.get("ExitTimestampLocal")
        )

        sw_pct, hw_pct = SleepReportParser._extract_sw_hw(raw, dur_ticks)

        return SleepSession(
            session_id=raw.get("SessionId", 0),
            entry_time_local=entry_local,
            exit_time_local=exit_local,
            duration_seconds=dur_seconds,
            sw_pct=sw_pct,
            hw_pct=hw_pct,
            on_ac=bool(raw.get("OnAc", False)),
            raw=raw,
        )

    @staticmethod
    def _extract_sw_hw(raw: dict, dur_ticks: int):
        """
        Extract SW% and HW% from the session ``Metadata`` block.

        The metadata for a Sleep session looks like::

            {
                "FriendlyName": "Detailed Session Information",
                "Values": [
                    {"Key": "Info.SwLowPowerStateTime", "Value": <int>},
                    {"Key": "Info.HwLowPowerStateTime", "Value": <int>},
                    ...
                ]
            }

        SW% = round(100 * sw_ticks / dur_ticks / 10)
        HW% = round(100 * hw_ticks / dur_ticks / 10)

        The ``/ 10`` factor is present in the original JS formula in the
        report: the metadata values are stored as "1000x ticks" relative
        to the session duration (i.e. they are in the same 100ns-tick unit
        but reported at a 10x scale).

        Returns:
            Tuple ``(sw_pct, hw_pct)`` — each is ``int | None``.
        """
        meta = raw.get("Metadata") or {}
        values = meta.get("Values", []) if isinstance(meta, dict) else []

        sw_ticks: Optional[int] = None
        hw_ticks: Optional[int] = None
        for item in values:
            key = item.get("Key", "")
            val = item.get("Value")
            if key == "Info.SwLowPowerStateTime":
                sw_ticks = val
            elif key == "Info.HwLowPowerStateTime":
                hw_ticks = val

        if sw_ticks is None or dur_ticks == 0:
            return None, None

        sw_pct = round(100 * sw_ticks / dur_ticks / 10)
        hw_pct = round(100 * hw_ticks / dur_ticks / 10) if hw_ticks is not None else None
        return sw_pct, hw_pct

    @staticmethod
    def _parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
        """
        Parse an ISO-8601 local-time string from the JSON (e.g.
        ``"2026-03-04T11:06:34"``).  Returns a timezone-naive
        :class:`datetime` or ``None``.
        """
        if not ts_str:
            return None
        # Strip trailing 'Z' or timezone offset — the *Local variants are
        # already in local time; we treat them as naive datetimes.
        ts_clean = ts_str.rstrip("Z").split("+")[0]
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
            try:
                return datetime.strptime(ts_clean, fmt)
            except ValueError:
                continue
        logger.warning("Cannot parse timestamp: %r", ts_str)
        return None

    @staticmethod
    def _resolve_dt_arg(dt: Union[str, datetime]) -> datetime:
        """
        Resolve *start* bound: pass a ``datetime`` through unchanged, or
        parse an ISO-8601 string via :meth:`_parse_dt_arg`.
        """
        if isinstance(dt, datetime):
            return dt
        return SleepReportParser._parse_dt_arg(dt)

    @staticmethod
    def _resolve_end_dt_arg(dt: Union[str, datetime]) -> datetime:
        """
        Resolve *end* bound: pass a ``datetime`` through unchanged, or
        parse an ISO-8601 string via :meth:`_parse_end_dt_arg`
        (date-only strings expand to ``23:59:59``).
        """
        if isinstance(dt, datetime):
            return dt
        return SleepReportParser._parse_end_dt_arg(dt)

    @staticmethod
    def _parse_dt_arg(dt_str: str) -> datetime:
        """
        Parse a user-supplied date/time filter argument (string only).

        Accepts:
        - ``"2026-03-04"``              → ``2026-03-04 00:00:00``
        - ``"2026-03-04T10:00:00"``
        - ``"2026-03-04 10:00:00"``

        Raises:
            :class:`~.exceptions.PHMLogParseError`: on invalid format.
        """
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        raise PHMLogParseError(
            f"Cannot parse date/time filter argument: {dt_str!r}. "
            "Expected ISO-8601 format, e.g. '2026-03-04' or '2026-03-04T10:00:00'."
        )

    @staticmethod
    def _parse_end_dt_arg(dt_str: str) -> datetime:
        """
        Parse a user-supplied *end* date/time filter argument.

        Identical to :meth:`_parse_dt_arg` except that a **date-only** string
        (``"YYYY-MM-DD"``) is expanded to end-of-day (``23:59:59``) so that
        all sessions on that calendar day are included.

        Accepts:
        - ``"2026-03-04"``              → ``2026-03-04 23:59:59``
        - ``"2026-03-04T10:00:00"``    → ``2026-03-04 10:00:00`` (unchanged)
        - ``"2026-03-04 10:00:00"``    → ``2026-03-04 10:00:00`` (unchanged)

        Raises:
            :class:`~.exceptions.PHMLogParseError`: on invalid format.
        """
        _DATE_ONLY_FMT = "%Y-%m-%d"
        # Check if it's a date-only string before trying all formats.
        try:
            dt = datetime.strptime(dt_str.strip(), _DATE_ONLY_FMT)
            return dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass
        # Fall through to the full datetime formats.
        return SleepReportParser._parse_dt_arg(dt_str)
