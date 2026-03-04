"""
Unit tests for SleepReportParser and SleepSession.

All tests use synthetic HTML/JSON fixtures — no network access and no
Playwright browser launch (the Playwright path is mocked or the regex
fallback is exercised via a pre-built fixture HTML file).
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lib.testtool.phm.sleep_report_parser import (
    SleepReportParser,
    SleepSession,
    SESSION_TYPE_SLEEP,
    _TICKS_PER_SECOND,
)
from lib.testtool.phm.exceptions import PHMLogParseError, PHMSleepReportParseError


# ---------------------------------------------------------------------------
# Helpers / small builders
# ---------------------------------------------------------------------------

def _make_sleep_scenario(
    session_id: int = 6,
    entry_local: str = "2026-03-04T11:06:34",
    exit_local: str = "2026-03-04T11:21:46",
    duration_seconds: float = 912.4,
    sw_pct: int = 98,
    hw_pct: int = 98,
    on_ac: bool = True,
) -> dict:
    """Build a minimal Sleep ScenarioInstance dict (Type=2)."""
    dur_ticks = int(duration_seconds * _TICKS_PER_SECOND)
    sw_ticks = int(sw_pct * dur_ticks * 10 / 100)
    hw_ticks = int(hw_pct * dur_ticks * 10 / 100)
    return {
        "Type": SESSION_TYPE_SLEEP,
        "SessionId": session_id,
        "EntryTimestampLocal": entry_local,
        "ExitTimestampLocal": exit_local,
        "Duration": dur_ticks,
        "OnAc": on_ac,
        "BatteryCountChanged": False,
        "Metadata": {
            "FriendlyName": "Detailed Session Information",
            "Values": [
                {"Key": "Info.SwLowPowerStateTime", "Value": sw_ticks},
                {"Key": "Info.HwLowPowerStateTime", "Value": hw_ticks},
            ],
        },
    }


def _make_sleep_scenario_no_meta(
    session_id: int = 10,
    entry_local: str = "2026-03-03T06:59:17",
    exit_local: str = "2026-03-03T06:59:27",
    duration_seconds: float = 9.5,
) -> dict:
    """Sleep session with no SW/HW metadata (short sleep)."""
    dur_ticks = int(duration_seconds * _TICKS_PER_SECOND)
    return {
        "Type": SESSION_TYPE_SLEEP,
        "SessionId": session_id,
        "EntryTimestampLocal": entry_local,
        "ExitTimestampLocal": exit_local,
        "Duration": dur_ticks,
        "OnAc": True,
        "BatteryCountChanged": False,
        "Metadata": {
            "FriendlyName": "Detailed Session Information",
            "Values": [],
        },
    }


def _make_active_scenario(session_id: int = 7) -> dict:
    """Non-sleep (Active = Type 0) session; should be filtered out."""
    return {
        "Type": 0,
        "SessionId": session_id,
        "EntryTimestampLocal": "2026-03-03T03:12:21",
        "ExitTimestampLocal": "2026-03-03T03:15:23",
        "Duration": 181303329,
        "OnAc": True,
        "BatteryCountChanged": False,
        "Metadata": {},
    }


def _make_spr_data(scenarios: list) -> dict:
    """Wrap scenarios in a minimal LocalSprData dict."""
    return {
        "ReportInformation": {
            "ReportVersion": "1.1",
            "ScanTimeLocal": "2026-03-04T12:22:02",
        },
        "SystemInformation": {},
        "Batteries": [],
        "EnergyDrains": [],
        "ScenarioInstances": scenarios,
    }


def _make_html_with_data(spr_data: dict) -> str:
    """Embed spr_data as ``LocalSprData`` in a minimal HTML page."""
    json_str = json.dumps(spr_data)
    return f"""<!DOCTYPE html>
<html lang="en">
<head><title>System Power Report</title></head>
<body>
<script>
    var LocalSprData = {json_str};
</script>
</body>
</html>
"""


@pytest.fixture
def sleep_html_file(tmp_path):
    """
    Write a synthetic sleep study HTML to a temp file.
    Contains sessions: SID=6 (Sleep, SW=100/HW=100), SID=7 (Active),
    SID=10 (Sleep, no meta), SID=21 (Sleep, SW=98/HW=98).
    """
    scenarios = [
        _make_sleep_scenario(
            session_id=6,
            entry_local="2026-03-02T02:59:20",
            exit_local="2026-03-03T03:12:26",
            duration_seconds=87186.9,
            sw_pct=100,
            hw_pct=100,
            on_ac=False,
        ),
        _make_active_scenario(session_id=7),
        _make_sleep_scenario_no_meta(
            session_id=10,
            entry_local="2026-03-03T06:59:17",
            exit_local="2026-03-03T06:59:27",
            duration_seconds=9.5,
        ),
        _make_sleep_scenario(
            session_id=21,
            entry_local="2026-03-04T11:06:34",
            exit_local="2026-03-04T11:21:46",
            duration_seconds=912.4,
            sw_pct=98,
            hw_pct=98,
            on_ac=True,
        ),
        _make_sleep_scenario(
            session_id=27,
            entry_local="2026-03-04T11:59:10",
            exit_local="2026-03-04T12:09:25",
            duration_seconds=62.0,
            sw_pct=0,
            hw_pct=0,
            on_ac=True,
        ),
    ]
    html = _make_html_with_data(_make_spr_data(scenarios))
    p = tmp_path / "sleepstudy-report.html"
    p.write_text(html, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# SleepSession dataclass tests
# ---------------------------------------------------------------------------

class TestSleepSession:
    """Unit tests for the SleepSession dataclass."""

    def test_defaults(self):
        s = SleepSession()
        assert s.session_id == 0
        assert s.duration_seconds == 0.0
        assert s.sw_pct is None
        assert s.hw_pct is None
        assert s.on_ac is False
        assert s.raw == {}

    def test_duration_hms_zero(self):
        s = SleepSession(duration_seconds=0)
        assert s.duration_hms == "0:00:00"

    def test_duration_hms_minutes_seconds(self):
        s = SleepSession(duration_seconds=3661)  # 1h 1m 1s
        assert s.duration_hms == "1:01:01"

    def test_duration_hms_large(self):
        s = SleepSession(duration_seconds=87186)  # ~24h
        assert ":" in s.duration_hms

    def test_repr_excludes_raw(self):
        # raw is repr=False; verify SleepSession repr does not include raw dict
        s = SleepSession(session_id=1, raw={"lots": "of data"})
        assert "raw" not in repr(s)


# ---------------------------------------------------------------------------
# SleepReportParser — file-not-found
# ---------------------------------------------------------------------------

class TestSleepReportParserInit:
    """Test constructor validation."""

    def test_raises_on_missing_file(self):
        with pytest.raises(PHMLogParseError, match="not found"):
            SleepReportParser("/nonexistent/path/report.html")

    def test_accepts_existing_file(self, sleep_html_file):
        parser = SleepReportParser(sleep_html_file)
        assert parser.html_path.exists()


# ---------------------------------------------------------------------------
# SleepReportParser — _extract_json_via_regex (no Playwright)
# ---------------------------------------------------------------------------

class TestExtractJsonViaRegex:
    """Test the regex-based JSON fallback directly."""

    def test_extracts_valid_json(self, sleep_html_file):
        parser = SleepReportParser(sleep_html_file)
        data = parser._extract_json_via_regex()
        assert isinstance(data, dict)
        assert "ScenarioInstances" in data

    def test_raises_on_missing_local_spr_data(self, tmp_path):
        html = "<html><body>No JSON here</body></html>"
        p = tmp_path / "bad.html"
        p.write_text(html, encoding="utf-8")
        parser = SleepReportParser(str(p))
        with pytest.raises(PHMLogParseError, match="LocalSprData"):
            parser._extract_json_via_regex()

    def test_raises_on_malformed_json(self, tmp_path):
        html = "    var LocalSprData = {bad json};\n"
        p = tmp_path / "bad.html"
        p.write_text(html, encoding="utf-8")
        parser = SleepReportParser(str(p))
        with pytest.raises(PHMLogParseError):
            parser._extract_json_via_regex()


# ---------------------------------------------------------------------------
# SleepReportParser — get_sleep_sessions (regex path, no browser)
# ---------------------------------------------------------------------------

class TestGetSleepSessions:
    """
    Test get_sleep_sessions() by patching _load_data to bypass Playwright.
    """

    def _make_parser_with_data(self, sleep_html_file, scenarios):
        parser = SleepReportParser(sleep_html_file)
        parser._raw_data = _make_spr_data(scenarios)
        return parser

    def test_returns_only_sleep_type(self, sleep_html_file):
        scenarios = [
            _make_sleep_scenario(session_id=6),
            _make_active_scenario(session_id=7),
        ]
        parser = self._make_parser_with_data(sleep_html_file, scenarios)
        sessions = parser.get_sleep_sessions()
        assert all(s.session_id != 7 for s in sessions)
        assert len(sessions) == 1
        assert sessions[0].session_id == 6

    def test_returns_all_sleep_all_types_filtered(self, sleep_html_file):
        scenarios = [
            _make_sleep_scenario(session_id=6, entry_local="2026-03-02T02:59:20"),
            _make_sleep_scenario(session_id=10, entry_local="2026-03-03T06:59:17"),
            _make_sleep_scenario(session_id=21, entry_local="2026-03-04T11:06:34"),
            _make_active_scenario(session_id=9),
        ]
        parser = self._make_parser_with_data(sleep_html_file, scenarios)
        sessions = parser.get_sleep_sessions()
        assert len(sessions) == 3

    def test_sorted_by_entry_time(self, sleep_html_file):
        scenarios = [
            _make_sleep_scenario(session_id=21, entry_local="2026-03-04T11:06:34"),
            _make_sleep_scenario(session_id=6, entry_local="2026-03-02T02:59:20"),
            _make_sleep_scenario(session_id=10, entry_local="2026-03-03T06:59:17"),
        ]
        parser = self._make_parser_with_data(sleep_html_file, scenarios)
        sessions = parser.get_sleep_sessions()
        ids = [s.session_id for s in sessions]
        assert ids == [6, 10, 21]

    def test_filter_by_date_only(self, sleep_html_file):
        scenarios = [
            _make_sleep_scenario(session_id=6, entry_local="2026-03-02T02:59:20"),
            _make_sleep_scenario(session_id=21, entry_local="2026-03-04T11:06:34"),
            _make_sleep_scenario(session_id=27, entry_local="2026-03-04T11:59:10"),
        ]
        parser = self._make_parser_with_data(sleep_html_file, scenarios)
        sessions = parser.get_sleep_sessions(start_dt="2026-03-04", end_dt="2026-03-04")
        assert all(s.entry_time_local.date() == datetime(2026, 3, 4).date() for s in sessions)
        assert len(sessions) == 2

    def test_filter_by_start_only(self, sleep_html_file):
        scenarios = [
            _make_sleep_scenario(session_id=6, entry_local="2026-03-02T02:59:20"),
            _make_sleep_scenario(session_id=21, entry_local="2026-03-04T11:06:34"),
        ]
        parser = self._make_parser_with_data(sleep_html_file, scenarios)
        sessions = parser.get_sleep_sessions(start_dt="2026-03-04T00:00:00")
        assert len(sessions) == 1
        assert sessions[0].session_id == 21

    def test_filter_by_end_only(self, sleep_html_file):
        scenarios = [
            _make_sleep_scenario(session_id=6, entry_local="2026-03-02T02:59:20"),
            _make_sleep_scenario(session_id=21, entry_local="2026-03-04T11:06:34"),
        ]
        parser = self._make_parser_with_data(sleep_html_file, scenarios)
        sessions = parser.get_sleep_sessions(end_dt="2026-03-03T23:59:59")
        assert len(sessions) == 1
        assert sessions[0].session_id == 6

    def test_no_match_returns_empty(self, sleep_html_file):
        scenarios = [
            _make_sleep_scenario(session_id=6, entry_local="2026-03-02T02:59:20"),
        ]
        parser = self._make_parser_with_data(sleep_html_file, scenarios)
        sessions = parser.get_sleep_sessions(
            start_dt="2026-03-05T00:00:00", end_dt="2026-03-05T23:59:59"
        )
        assert sessions == []

    def test_empty_scenarios_returns_empty(self, sleep_html_file):
        parser = self._make_parser_with_data(sleep_html_file, [])
        sessions = parser.get_sleep_sessions()
        assert sessions == []

    def test_filter_with_datetime_objects(self, sleep_html_file):
        """start_dt / end_dt accept datetime objects directly."""
        scenarios = [
            _make_sleep_scenario(session_id=6,  entry_local="2026-03-02T02:59:20"),
            _make_sleep_scenario(session_id=21, entry_local="2026-03-04T11:06:34"),
            _make_sleep_scenario(session_id=27, entry_local="2026-03-04T11:59:10"),
        ]
        parser = self._make_parser_with_data(sleep_html_file, scenarios)
        sessions = parser.get_sleep_sessions(
            start_dt=datetime(2026, 3, 4, 11, 0, 0),
            end_dt=datetime(2026, 3, 4, 11, 30, 0),
        )
        assert len(sessions) == 1
        assert sessions[0].session_id == 21

    def test_filter_mixed_str_and_datetime(self, sleep_html_file):
        """start_dt as datetime, end_dt as string — both should work."""
        scenarios = [
            _make_sleep_scenario(session_id=6,  entry_local="2026-03-02T02:59:20"),
            _make_sleep_scenario(session_id=21, entry_local="2026-03-04T11:06:34"),
        ]
        parser = self._make_parser_with_data(sleep_html_file, scenarios)
        sessions = parser.get_sleep_sessions(
            start_dt=datetime(2026, 3, 4),
            end_dt="2026-03-04",  # date-only → expands to 23:59:59
        )
        assert len(sessions) == 1
        assert sessions[0].session_id == 21


# ---------------------------------------------------------------------------
# SW / HW percentage extraction
# ---------------------------------------------------------------------------

class TestExtractSwHw:
    """Unit tests for _extract_sw_hw static method."""

    def test_sw_hw_100_percent(self):
        dur_ticks = int(100 * _TICKS_PER_SECOND)
        raw = _make_sleep_scenario(
            duration_seconds=100, sw_pct=100, hw_pct=100
        )
        sw, hw = SleepReportParser._extract_sw_hw(raw, dur_ticks)
        assert sw == 100
        assert hw == 100

    def test_sw_hw_98_percent(self):
        dur_ticks = int(912.4 * _TICKS_PER_SECOND)
        raw = _make_sleep_scenario(
            duration_seconds=912.4, sw_pct=98, hw_pct=98
        )
        sw, hw = SleepReportParser._extract_sw_hw(raw, dur_ticks)
        assert sw == 98
        assert hw == 98

    def test_sw_hw_zero_percent(self):
        dur_ticks = int(62.0 * _TICKS_PER_SECOND)
        raw = _make_sleep_scenario(
            duration_seconds=62.0, sw_pct=0, hw_pct=0
        )
        sw, hw = SleepReportParser._extract_sw_hw(raw, dur_ticks)
        assert sw == 0

    def test_no_metadata_returns_none(self):
        raw = _make_sleep_scenario_no_meta()
        dur_ticks = int(9.5 * _TICKS_PER_SECOND)
        sw, hw = SleepReportParser._extract_sw_hw(raw, dur_ticks)
        assert sw is None
        assert hw is None

    def test_zero_duration_returns_none(self):
        # Guard against division-by-zero
        raw = _make_sleep_scenario(duration_seconds=100, sw_pct=50, hw_pct=50)
        sw, hw = SleepReportParser._extract_sw_hw(raw, 0)
        assert sw is None
        assert hw is None

    def test_missing_hw_only(self):
        """SW present but HW key absent → hw_pct should be None."""
        dur_ticks = int(100 * _TICKS_PER_SECOND)
        raw = {
            "Type": SESSION_TYPE_SLEEP,
            "SessionId": 99,
            "Duration": dur_ticks,
            "Metadata": {
                "Values": [
                    {"Key": "Info.SwLowPowerStateTime", "Value": int(50 * dur_ticks * 10 / 100)},
                ]
            },
        }
        sw, hw = SleepReportParser._extract_sw_hw(raw, dur_ticks)
        assert sw == 50
        assert hw is None


# ---------------------------------------------------------------------------
# _parse_timestamp and _parse_dt_arg
# ---------------------------------------------------------------------------

class TestParseTimestamp:
    def test_valid_iso_datetime(self):
        dt = SleepReportParser._parse_timestamp("2026-03-04T11:06:34")
        assert dt == datetime(2026, 3, 4, 11, 6, 34)

    def test_valid_iso_with_z(self):
        dt = SleepReportParser._parse_timestamp("2026-03-04T11:06:34Z")
        assert dt == datetime(2026, 3, 4, 11, 6, 34)

    def test_none_returns_none(self):
        assert SleepReportParser._parse_timestamp(None) is None

    def test_empty_string_returns_none(self):
        assert SleepReportParser._parse_timestamp("") is None


class TestParseDtArg:
    def test_date_only(self):
        dt = SleepReportParser._parse_dt_arg("2026-03-04")
        assert dt == datetime(2026, 3, 4, 0, 0, 0)

    def test_date_time_t_separator(self):
        dt = SleepReportParser._parse_dt_arg("2026-03-04T10:30:00")
        assert dt == datetime(2026, 3, 4, 10, 30, 0)

    def test_date_time_space_separator(self):
        dt = SleepReportParser._parse_dt_arg("2026-03-04 10:30:00")
        assert dt == datetime(2026, 3, 4, 10, 30, 0)

    def test_invalid_format_raises(self):
        with pytest.raises(PHMLogParseError, match="Cannot parse"):
            SleepReportParser._parse_dt_arg("03/04/2026")


class TestParseEndDtArg:
    def test_date_only_expands_to_end_of_day(self):
        dt = SleepReportParser._parse_end_dt_arg("2026-03-04")
        assert dt == datetime(2026, 3, 4, 23, 59, 59)

    def test_datetime_with_time_unchanged(self):
        dt = SleepReportParser._parse_end_dt_arg("2026-03-04T10:30:00")
        assert dt == datetime(2026, 3, 4, 10, 30, 0)

    def test_invalid_format_raises(self):
        with pytest.raises(PHMLogParseError, match="Cannot parse"):
            SleepReportParser._parse_end_dt_arg("03/04/2026")


class TestResolveDtArg:
    """_resolve_dt_arg / _resolve_end_dt_arg accept str OR datetime."""

    def test_string_start_parsed(self):
        dt = SleepReportParser._resolve_dt_arg("2026-03-04T10:30:00")
        assert dt == datetime(2026, 3, 4, 10, 30, 0)

    def test_datetime_start_returned_unchanged(self):
        input_dt = datetime(2026, 3, 4, 10, 30, 0)
        assert SleepReportParser._resolve_dt_arg(input_dt) is input_dt

    def test_invalid_string_start_raises(self):
        with pytest.raises(PHMLogParseError):
            SleepReportParser._resolve_dt_arg("03/04/2026")

    def test_string_end_date_only_expands_to_eod(self):
        dt = SleepReportParser._resolve_end_dt_arg("2026-03-04")
        assert dt == datetime(2026, 3, 4, 23, 59, 59)

    def test_string_end_with_time_unchanged(self):
        dt = SleepReportParser._resolve_end_dt_arg("2026-03-04T10:30:00")
        assert dt == datetime(2026, 3, 4, 10, 30, 0)

    def test_datetime_end_returned_unchanged(self):
        input_dt = datetime(2026, 3, 4, 15, 0, 0)
        assert SleepReportParser._resolve_end_dt_arg(input_dt) is input_dt

    def test_invalid_string_end_raises(self):
        with pytest.raises(PHMLogParseError):
            SleepReportParser._resolve_end_dt_arg("03/04/2026")


# ---------------------------------------------------------------------------
# _build_session
# ---------------------------------------------------------------------------

class TestBuildSession:
    def test_session_id_set(self):
        raw = _make_sleep_scenario(session_id=21)
        s = SleepReportParser._build_session(raw)
        assert s.session_id == 21

    def test_duration_seconds_calculated(self):
        raw = _make_sleep_scenario(duration_seconds=912.4)
        s = SleepReportParser._build_session(raw)
        assert abs(s.duration_seconds - 912.4) < 0.5

    def test_sw_hw_extracted(self):
        raw = _make_sleep_scenario(sw_pct=98, hw_pct=98)
        s = SleepReportParser._build_session(raw)
        assert s.sw_pct == 98
        assert s.hw_pct == 98

    def test_on_ac_true(self):
        raw = _make_sleep_scenario(on_ac=True)
        s = SleepReportParser._build_session(raw)
        assert s.on_ac is True

    def test_on_ac_false(self):
        raw = _make_sleep_scenario(on_ac=False)
        s = SleepReportParser._build_session(raw)
        assert s.on_ac is False

    def test_entry_exit_time_parsed(self):
        raw = _make_sleep_scenario(
            entry_local="2026-03-04T11:06:34",
            exit_local="2026-03-04T11:21:46",
        )
        s = SleepReportParser._build_session(raw)
        assert s.entry_time_local == datetime(2026, 3, 4, 11, 6, 34)
        assert s.exit_time_local == datetime(2026, 3, 4, 11, 21, 46)

    def test_raw_preserved(self):
        raw = _make_sleep_scenario(session_id=99)
        s = SleepReportParser._build_session(raw)
        assert s.raw is raw


# ---------------------------------------------------------------------------
# Playwright path: mock _extract_json_via_playwright to return fixture data
# ---------------------------------------------------------------------------

class TestGetSleepSessionsViaPlaywright:
    """
    Verify that get_sleep_sessions() uses the Playwright fallback when the
    regex path fails, and that it correctly filters sessions from the
    Playwright-returned data.

    Both tests simulate regex failure so that _load_data() falls through
    to _extract_json_via_playwright(), which is then mocked to return
    controlled fixture data (no real browser is launched).
    """

    def _regex_fail(self):
        raise PHMLogParseError("simulated regex failure")

    def test_playwright_fallback_returns_sessions(self, sleep_html_file):
        spr_data = _make_spr_data([
            _make_sleep_scenario(
                session_id=21,
                entry_local="2026-03-04T11:06:34",
                sw_pct=98,
                hw_pct=98,
            ),
        ])
        parser = SleepReportParser(sleep_html_file)
        with patch.object(parser, "_extract_json_via_regex", side_effect=self._regex_fail):
            with patch.object(parser, "_extract_json_via_playwright", return_value=spr_data):
                sessions = parser.get_sleep_sessions(start_dt="2026-03-04")
        assert len(sessions) == 1
        assert sessions[0].sw_pct == 98
        assert sessions[0].hw_pct == 98

    def test_playwright_fallback_filter_by_range(self, sleep_html_file):
        spr_data = _make_spr_data([
            _make_sleep_scenario(session_id=6,  entry_local="2026-03-02T02:59:20"),
            _make_sleep_scenario(session_id=21, entry_local="2026-03-04T11:06:34"),
            _make_sleep_scenario(session_id=27, entry_local="2026-03-04T11:59:10"),
        ])
        parser = SleepReportParser(sleep_html_file)
        with patch.object(parser, "_extract_json_via_regex", side_effect=self._regex_fail):
            with patch.object(parser, "_extract_json_via_playwright", return_value=spr_data):
                sessions = parser.get_sleep_sessions(
                    start_dt="2026-03-04T11:00:00",
                    end_dt="2026-03-04T11:30:00",
                )
        assert len(sessions) == 1
        assert sessions[0].session_id == 21


# ---------------------------------------------------------------------------
# Import / export smoke test
# ---------------------------------------------------------------------------

def test_imports_from_phm_package():
    """Verify the new classes are re-exported from the top-level phm package."""
    from lib.testtool.phm import SleepReportParser, SleepSession, PHMSleepReportParseError
    assert SleepReportParser is not None
    assert SleepSession is not None
    assert PHMSleepReportParseError is not None
