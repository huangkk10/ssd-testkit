"""
Integration tests for SleepReportParser using the real
``tmp/sleepstudy-report.html`` file shipped with the workspace.

These tests launch a real Playwright Chromium browser to load the HTML and
extract session data -- exercising the full production path.

Run with::

    pytest tests/integration/lib/testtool/test_sleepstudy/test_sleep_report_parser_integration.py -v

Requirements
------------
- ``playwright`` package installed: ``pip install playwright``
- Chromium browser installed: ``playwright install chromium``
- The file ``tmp/sleepstudy-report.html`` must exist in the workspace root.

Markers
-------
- ``integration``         -- real file I/O and Playwright browser launch
- ``slow``                -- browser startup adds ~5-10 s of overhead
- ``requires_sleepstudy`` -- requires the sleepstudy HTML report
"""

import pytest
from datetime import datetime
from pathlib import Path

from lib.testtool.sleepstudy.sleep_report_parser import SleepReportParser, SleepSession
from lib.testtool.sleepstudy.exceptions import SleepStudyLogParseError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser(real_html_path) -> SleepReportParser:
    """Module-scoped parser so the HTML is only loaded once."""
    return SleepReportParser(real_html_path)


@pytest.fixture(scope="module")
def all_sleep_sessions(parser):
    """All Sleep sessions from the real report (no date filter)."""
    return parser.get_sleep_sessions()


# ---------------------------------------------------------------------------
# Smoke: parser construction
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_sleepstudy
class TestParserConstruction:
    def test_parser_accepts_real_file(self, real_html_path):
        p = SleepReportParser(real_html_path)
        assert p.html_path.exists()

    def test_missing_file_raises(self):
        with pytest.raises(SleepStudyLogParseError, match="not found"):
            SleepReportParser("/nonexistent/sleepstudy.html")


# ---------------------------------------------------------------------------
# Data extraction: all sleep sessions (no filter)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_sleepstudy
class TestAllSleepSessions:
    """Validate data extracted from the real HTML report."""

    def test_returns_list(self, all_sleep_sessions):
        assert isinstance(all_sleep_sessions, list)

    def test_only_sleep_type_sessions(self, all_sleep_sessions):
        assert len(all_sleep_sessions) > 0, "Expected at least one Sleep session"

    def test_session_ids_are_positive(self, all_sleep_sessions):
        for s in all_sleep_sessions:
            assert s.session_id > 0, f"Expected positive session_id, got {s.session_id}"

    def test_duration_positive(self, all_sleep_sessions):
        for s in all_sleep_sessions:
            assert s.duration_seconds >= 0

    def test_entry_times_are_datetime(self, all_sleep_sessions):
        for s in all_sleep_sessions:
            assert isinstance(s.entry_time_local, datetime)

    def test_sessions_sorted_ascending(self, all_sleep_sessions):
        times = [s.entry_time_local for s in all_sleep_sessions]
        assert times == sorted(times)

    def test_known_session_sid6_present(self, all_sleep_sessions):
        """Session 6 is a ~24-hour sleep from 2026-03-02 with SW=100% HW=100%."""
        sid6 = next((s for s in all_sleep_sessions if s.session_id == 6), None)
        assert sid6 is not None, "Session 6 not found"
        assert sid6.sw_pct == 100
        assert sid6.hw_pct == 100
        assert sid6.duration_seconds > 80_000

    def test_known_session_sid21_present(self, all_sleep_sessions):
        """Session 21 is a ~91-second sleep on 2026-03-04 with SW=98% HW=98%."""
        sid21 = next((s for s in all_sleep_sessions if s.session_id == 21), None)
        assert sid21 is not None, "Session 21 not found"
        assert sid21.sw_pct == 98
        assert sid21.hw_pct == 98

    def test_known_session_sid27_sw_zero(self, all_sleep_sessions):
        """Session 27 is a short sleep on 2026-03-04 with SW=0%."""
        sid27 = next((s for s in all_sleep_sessions if s.session_id == 27), None)
        assert sid27 is not None, "Session 27 not found"
        assert sid27.sw_pct == 0

    def test_sessions_without_sw_hw_have_none(self, all_sleep_sessions):
        """Sessions 10, 15, 18, 24 have no SW/HW metadata."""
        no_meta_ids = {10, 15, 18, 24}
        for s in all_sleep_sessions:
            if s.session_id in no_meta_ids:
                assert s.sw_pct is None, (
                    f"Session {s.session_id}: expected sw_pct=None, got {s.sw_pct}"
                )


# ---------------------------------------------------------------------------
# Date/time filtering
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_sleepstudy
class TestDateTimeFilter:
    """Verify date/time range filtering against the real report."""

    def test_filter_2026_03_04_returns_subset(self, parser):
        sessions = parser.get_sleep_sessions(
            start_dt="2026-03-04",
            end_dt="2026-03-04",
        )
        assert len(sessions) > 0
        for s in sessions:
            assert s.entry_time_local.date() == datetime(2026, 3, 4).date()

    def test_filter_exact_range_sid21(self, parser):
        """Filter to the window containing only SID=21 (11:06-11:21 on 2026-03-04)."""
        sessions = parser.get_sleep_sessions(
            start_dt="2026-03-04T11:00:00",
            end_dt="2026-03-04T11:30:00",
        )
        ids = [s.session_id for s in sessions]
        assert 21 in ids, f"Session 21 not found in {ids}"

    def test_filter_future_date_returns_empty(self, parser):
        sessions = parser.get_sleep_sessions(
            start_dt="2099-01-01",
            end_dt="2099-12-31",
        )
        assert sessions == []

    def test_filter_no_args_returns_all_sleep(self, parser, all_sleep_sessions):
        sessions = parser.get_sleep_sessions()
        assert len(sessions) == len(all_sleep_sessions)

    def test_start_dt_date_only_format(self, parser):
        sessions = parser.get_sleep_sessions(start_dt="2026-03-04")
        assert isinstance(sessions, list)

    def test_invalid_start_dt_raises(self, real_html_path):
        p = SleepReportParser(real_html_path)
        with pytest.raises(SleepStudyLogParseError, match="Cannot parse"):
            p.get_sleep_sessions(start_dt="04-03-2026")

    def test_filter_2026_03_02_has_sid6(self, parser):
        sessions = parser.get_sleep_sessions(
            start_dt="2026-03-02",
            end_dt="2026-03-02",
        )
        ids = [s.session_id for s in sessions]
        assert 6 in ids, f"Session 6 not found in {ids}"

    def test_filter_with_datetime_objects(self, parser):
        """datetime objects accepted directly -- same result as equivalent strings."""
        sessions_str = parser.get_sleep_sessions(
            start_dt="2026-03-04T11:00:00",
            end_dt="2026-03-04T11:30:00",
        )
        sessions_dt = parser.get_sleep_sessions(
            start_dt=datetime(2026, 3, 4, 11, 0, 0),
            end_dt=datetime(2026, 3, 4, 11, 30, 0),
        )
        assert [s.session_id for s in sessions_str] == [s.session_id for s in sessions_dt]

    def test_filter_mixed_str_and_datetime(self, parser):
        sessions = parser.get_sleep_sessions(
            start_dt=datetime(2026, 3, 4),
            end_dt="2026-03-04",
        )
        assert len(sessions) > 0
        for s in sessions:
            assert s.entry_time_local.date() == datetime(2026, 3, 4).date()


# ---------------------------------------------------------------------------
# SleepSession properties
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_sleepstudy
class TestSleepSessionProperties:
    def test_duration_hms_format(self, all_sleep_sessions):
        for s in all_sleep_sessions:
            hms = s.duration_hms
            parts = hms.split(":")
            assert len(parts) == 3, f"duration_hms '{hms}' should have 3 parts"
            assert int(parts[1]) < 60
            assert int(parts[2]) < 60

    def test_on_ac_is_bool(self, all_sleep_sessions):
        for s in all_sleep_sessions:
            assert isinstance(s.on_ac, bool)

    def test_sw_hw_pct_in_range(self, all_sleep_sessions):
        for s in all_sleep_sessions:
            if s.sw_pct is not None:
                assert 0 <= s.sw_pct <= 100
            if s.hw_pct is not None:
                assert 0 <= s.hw_pct <= 100

    def test_raw_dict_populated(self, all_sleep_sessions):
        for s in all_sleep_sessions:
            assert isinstance(s.raw, dict)
            assert "Type" in s.raw


# ---------------------------------------------------------------------------
# Caching: loading data twice calls extraction only once
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_sleepstudy
class TestDataCaching:
    def test_raw_data_cached_after_first_load(self, real_html_path):
        from unittest.mock import patch
        parser = SleepReportParser(real_html_path)
        sessions_a = parser.get_sleep_sessions()
        with patch.object(
            parser, "_extract_json_via_regex",
            side_effect=AssertionError("Should not be called again")
        ):
            with patch.object(
                parser, "_extract_json_via_playwright",
                side_effect=AssertionError("Should not be called again")
            ):
                sessions_b = parser.get_sleep_sessions()
        assert len(sessions_a) == len(sessions_b)
