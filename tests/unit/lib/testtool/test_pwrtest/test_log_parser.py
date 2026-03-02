"""
Unit tests for PwrTestLogParser and PwrTestTestResult.
Uses fixture log strings written to temp directories — no real executables.
"""

import os
import pytest
from lib.testtool.pwrtest.log_parser import (
    PwrTestLogParser,
    PwrTestTestResult,
    PwrTestTransitionResult,
)
from lib.testtool.pwrtest.exceptions import PwrTestLogParseError

# Import shared log content from conftest
from .conftest import PASS_LOG, FAIL_LOG


# ---------------------------------------------------------------------------
# PwrTestTestResult dataclass
# ---------------------------------------------------------------------------

class TestPwrTestTestResult:

    def test_default_status_unknown(self):
        r = PwrTestTestResult()
        assert r.status == 'UNKNOWN'

    def test_default_errors_empty_list(self):
        r = PwrTestTestResult()
        assert r.errors == []

    def test_default_transitions_empty(self):
        r = PwrTestTestResult()
        assert r.transitions == []

    def test_default_cycles_zero(self):
        r = PwrTestTestResult()
        assert r.total_cycles == 0
        assert r.completed_cycles == 0

    def test_default_raw_path_empty(self):
        r = PwrTestTestResult()
        assert r.raw_report_path == ''


# ---------------------------------------------------------------------------
# PwrTestTransitionResult dataclass
# ---------------------------------------------------------------------------

class TestPwrTestTransitionResult:

    def test_defaults(self):
        t = PwrTestTransitionResult()
        assert t.transition_number == 0
        assert t.total_transitions == 0
        assert t.target_state == ''
        assert t.completed is False
        assert t.sleep_time_ms is None


# ---------------------------------------------------------------------------
# PwrTestLogParser — parse_log — PASS
# ---------------------------------------------------------------------------

class TestLogParserPass:

    def test_parse_status_pass(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.status == 'PASS'

    def test_parse_pass_no_errors(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.errors == []

    def test_parse_pass_cycle_counts(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.total_cycles == 1
        assert result.completed_cycles == 1

    def test_parse_pass_transition_count(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert len(result.transitions) == 1

    def test_parse_pass_target_state(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.transitions[0].target_state == 'S3'

    def test_parse_pass_effective_state(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.transitions[0].effective_state == 'S3'

    def test_parse_pass_sleep_time_ms(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.transitions[0].sleep_time_ms == 1134

    def test_parse_pass_bios_init_time_ms(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.transitions[0].bios_init_time_ms == 3242

    def test_parse_pass_driver_wake_time_ms(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.transitions[0].driver_wake_time_ms == 442

    def test_parse_pass_start_time_set(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.transitions[0].start_time != ''

    def test_parse_pass_end_time_set(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.transitions[0].end_time != ''

    def test_parse_pass_transition_completed(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.transitions[0].completed is True

    def test_parse_pass_raw_report_path_set(self, pass_log_file):
        result = PwrTestLogParser().parse_log(pass_log_file)
        assert result.raw_report_path != ''


# ---------------------------------------------------------------------------
# PwrTestLogParser — parse_log — FAIL
# ---------------------------------------------------------------------------

class TestLogParserFail:

    def test_parse_status_fail(self, fail_log_file):
        result = PwrTestLogParser().parse_log(fail_log_file)
        assert result.status == 'FAIL'

    def test_parse_fail_has_errors(self, fail_log_file):
        result = PwrTestLogParser().parse_log(fail_log_file)
        assert len(result.errors) > 0

    def test_parse_fail_partial_cycles(self, fail_log_file):
        result = PwrTestLogParser().parse_log(fail_log_file)
        # 2 total, only 1 completed
        assert result.total_cycles == 2
        assert result.completed_cycles < result.total_cycles


# ---------------------------------------------------------------------------
# PwrTestLogParser — parse_report auto-detect
# ---------------------------------------------------------------------------

class TestLogParserParseReport:

    def test_parse_report_log_extension(self, pass_log_file):
        result = PwrTestLogParser().parse_report(pass_log_file)
        assert result.status == 'PASS'

    def test_parse_report_unsupported_extension(self, tmp_path):
        p = tmp_path / 'report.csv'
        p.write_text('some,data', encoding='utf-8')
        with pytest.raises(PwrTestLogParseError, match="Unsupported"):
            PwrTestLogParser().parse_report(str(p))


# ---------------------------------------------------------------------------
# PwrTestLogParser — error handling
# ---------------------------------------------------------------------------

class TestLogParserErrors:

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(PwrTestLogParseError, match="not found"):
            PwrTestLogParser().parse_log(str(tmp_path / 'missing.log'))

    def test_empty_file_raises(self, tmp_path):
        p = tmp_path / 'empty.log'
        p.write_text('', encoding='utf-8')
        with pytest.raises(PwrTestLogParseError, match="empty"):
            PwrTestLogParser().parse_log(str(p))

    def test_whitespace_only_file_raises(self, tmp_path):
        p = tmp_path / 'ws.log'
        p.write_text('   \n\n  ', encoding='utf-8')
        with pytest.raises(PwrTestLogParseError, match="empty"):
            PwrTestLogParser().parse_log(str(p))

    def test_no_verdict_yields_unknown(self, tmp_path):
        p = tmp_path / 'novrd.log'
        p.write_text('Start: PwrTest\nSome irrelevant lines\n', encoding='utf-8')
        result = PwrTestLogParser().parse_log(str(p))
        assert result.status == 'UNKNOWN'


# ---------------------------------------------------------------------------
# PwrTestLogParser — parse_reports_batch
# ---------------------------------------------------------------------------

class TestLogParserBatch:

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(PwrTestLogParseError):
            PwrTestLogParser().parse_reports_batch(str(tmp_path / 'no_such_dir'))

    def test_empty_directory_returns_empty_list(self, tmp_path):
        results = PwrTestLogParser().parse_reports_batch(str(tmp_path))
        assert results == []

    def test_batch_multiple_log_files(self, tmp_path):
        for i in range(3):
            (tmp_path / f'pwrtestlog_{i}.log').write_text(PASS_LOG, encoding='utf-8')
        results = PwrTestLogParser().parse_reports_batch(str(tmp_path), pattern='*.log')
        assert len(results) == 3

    def test_batch_all_pass(self, tmp_path):
        for i in range(2):
            (tmp_path / f'pwrtestlog_{i}.log').write_text(PASS_LOG, encoding='utf-8')
        results = PwrTestLogParser().parse_reports_batch(str(tmp_path), pattern='*.log')
        assert all(r.status == 'PASS' for r in results)


# ---------------------------------------------------------------------------
# PwrTestLogParser — summarize
# ---------------------------------------------------------------------------

class TestLogParserSummarize:

    def test_summarize_counts(self):
        results = [
            PwrTestTestResult(status='PASS', total_cycles=1, completed_cycles=1),
            PwrTestTestResult(status='PASS', total_cycles=1, completed_cycles=1),
            PwrTestTestResult(status='FAIL', total_cycles=2, completed_cycles=1),
            PwrTestTestResult(status='UNKNOWN'),
        ]
        summary = PwrTestLogParser.summarize(results)
        assert summary['total']   == 4
        assert summary['pass']    == 2
        assert summary['fail']    == 1
        assert summary['unknown'] == 1

    def test_summarize_cycle_totals(self):
        results = [
            PwrTestTestResult(status='PASS', total_cycles=1, completed_cycles=1),
            PwrTestTestResult(status='FAIL', total_cycles=2, completed_cycles=1),
        ]
        summary = PwrTestLogParser.summarize(results)
        assert summary['total_cycles']     == 3
        assert summary['completed_cycles'] == 2

    def test_summarize_empty(self):
        summary = PwrTestLogParser.summarize([])
        assert summary['total'] == 0
        assert summary['error_summary'] == []
