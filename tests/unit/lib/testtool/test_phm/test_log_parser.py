"""
Unit tests for PHMLogParser and PHMTestResult.
Uses fixture HTML strings — no real files on disk except via temp_dir fixtures.
"""

import os
import pytest
from lib.testtool.phm.log_parser import PHMLogParser, PHMTestResult
from lib.testtool.phm.exceptions import PHMLogParseError


class TestPHMTestResult:
    """Verify PHMTestResult dataclass defaults."""

    def test_default_status_unknown(self):
        r = PHMTestResult()
        assert r.status == 'UNKNOWN'

    def test_default_errors_empty_list(self):
        r = PHMTestResult()
        assert r.errors == []

    def test_default_cycles_zero(self):
        r = PHMTestResult()
        assert r.total_cycles == 0
        assert r.completed_cycles == 0


class TestPHMLogParser:
    """Test suite for PHMLogParser."""

    # ------------------------------------------------------------------
    # parse_html_report — PASS case
    # ------------------------------------------------------------------

    def test_parse_pass_report_status(self, html_pass_file):
        parser = PHMLogParser()
        result = parser.parse_html_report(html_pass_file)
        assert result.status == 'PASS'

    def test_parse_pass_report_no_errors(self, html_pass_file):
        parser = PHMLogParser()
        result = parser.parse_html_report(html_pass_file)
        assert result.errors == []

    def test_parse_pass_report_cycles(self, html_pass_file):
        parser = PHMLogParser()
        result = parser.parse_html_report(html_pass_file)
        assert result.total_cycles == 10
        assert result.completed_cycles == 10

    def test_parse_pass_report_timestamps(self, html_pass_file):
        parser = PHMLogParser()
        result = parser.parse_html_report(html_pass_file)
        assert result.start_time is not None
        assert result.end_time is not None

    def test_parse_pass_report_raw_path_set(self, html_pass_file):
        parser = PHMLogParser()
        result = parser.parse_html_report(html_pass_file)
        assert result.raw_html_path != ''

    def test_parse_pass_report_test_name(self, html_pass_file):
        parser = PHMLogParser()
        result = parser.parse_html_report(html_pass_file)
        assert 'Powerhouse' in result.test_name

    # ------------------------------------------------------------------
    # parse_html_report — FAIL case
    # ------------------------------------------------------------------

    def test_parse_fail_report_status(self, html_fail_file):
        parser = PHMLogParser()
        result = parser.parse_html_report(html_fail_file)
        assert result.status == 'FAIL'

    def test_parse_fail_report_has_errors(self, html_fail_file):
        parser = PHMLogParser()
        result = parser.parse_html_report(html_fail_file)
        assert len(result.errors) > 0

    def test_parse_fail_report_error_content(self, html_fail_file):
        parser = PHMLogParser()
        result = parser.parse_html_report(html_fail_file)
        combined = ' '.join(result.errors)
        assert 'S0ix' in combined or 'Power loss' in combined or 'cycle' in combined.lower()

    def test_parse_fail_report_completed_less_than_total(self, html_fail_file):
        parser = PHMLogParser()
        result = parser.parse_html_report(html_fail_file)
        assert result.completed_cycles < result.total_cycles

    # ------------------------------------------------------------------
    # parse_html_report — error cases
    # ------------------------------------------------------------------

    def test_file_not_found_raises(self):
        parser = PHMLogParser()
        with pytest.raises(PHMLogParseError, match="not found"):
            parser.parse_html_report('./nonexistent/path/report.html')

    def test_empty_file_raises(self, temp_dir):
        empty_file = os.path.join(temp_dir, 'empty.html')
        open(empty_file, 'w').close()
        parser = PHMLogParser()
        with pytest.raises(PHMLogParseError, match="empty"):
            parser.parse_html_report(empty_file)

    def test_whitespace_only_file_raises(self, temp_dir):
        path = os.path.join(temp_dir, 'whitespace.html')
        with open(path, 'w') as f:
            f.write('   \n\n  ')
        parser = PHMLogParser()
        with pytest.raises(PHMLogParseError):
            parser.parse_html_report(path)

    def test_garbage_html_returns_unknown(self, temp_dir):
        path = os.path.join(temp_dir, 'garbage.html')
        with open(path, 'w') as f:
            f.write('<html><body>No useful content here at all.</body></html>')
        parser = PHMLogParser()
        result = parser.parse_html_report(path)
        assert result.status == 'UNKNOWN'

    # ------------------------------------------------------------------
    # parse_html_reports_batch
    # ------------------------------------------------------------------

    def test_batch_returns_list(self, temp_dir, sample_html_pass, sample_html_fail):
        for i, html in enumerate([sample_html_pass, sample_html_fail]):
            with open(os.path.join(temp_dir, f'report_{i}.html'), 'w') as f:
                f.write(html)

        parser = PHMLogParser()
        results = parser.parse_html_reports_batch(temp_dir)
        assert isinstance(results, list)
        assert len(results) == 2

    def test_batch_empty_dir_returns_empty_list(self, temp_dir):
        parser = PHMLogParser()
        results = parser.parse_html_reports_batch(temp_dir)
        assert results == []

    def test_batch_missing_dir_raises(self):
        parser = PHMLogParser()
        with pytest.raises(PHMLogParseError, match="not found"):
            parser.parse_html_reports_batch('./no/such/dir')

    # ------------------------------------------------------------------
    # summarize
    # ------------------------------------------------------------------

    def test_summarize_counts(self, html_pass_file, html_fail_file):
        parser = PHMLogParser()
        results = [
            parser.parse_html_report(html_pass_file),
            parser.parse_html_report(html_fail_file),
        ]
        summary = PHMLogParser.summarize(results)
        assert summary['total'] == 2
        assert summary['pass'] == 1
        assert summary['fail'] == 1
        assert 'error_summary' in summary

    def test_summarize_empty_list(self):
        summary = PHMLogParser.summarize([])
        assert summary['total'] == 0
        assert summary['pass'] == 0
        assert summary['fail'] == 0
