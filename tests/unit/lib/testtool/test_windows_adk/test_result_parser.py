"""
Unit tests for windows_adk result_parser module.
"""

import os
import pytest
from unittest.mock import patch

from lib.testtool.windows_adk.exceptions import ADKResultError
from lib.testtool.windows_adk.result_parser import (
    check_result_bios_post_time,
    check_result_bpfs,
    check_result_hiberfile_read,
    check_result_standby,
    get_result_average,
    get_result_bios_post_time,
    get_result_hiberfile_read,
    parse_axelog,
)


# ---------------------------------------------------------------------------
# parse_axelog
# ---------------------------------------------------------------------------

class TestParseAxelog:
    def test_exit_code_0_returns_passed(self, axelog_passed):
        ok, msg = parse_axelog(axelog_passed)
        assert ok is True
        assert "Passed" in msg

    def test_missing_exit_code_returns_failed(self, axelog_failed):
        ok, msg = parse_axelog(axelog_failed)
        assert ok is False
        assert "Failed" in msg

    def test_file_not_found_returns_false(self, temp_dir):
        ok, msg = parse_axelog(os.path.join(temp_dir, "nonexistent.txt"))
        assert ok is False
        assert msg  # some error message


# ---------------------------------------------------------------------------
# get_result_average
# ---------------------------------------------------------------------------

class TestGetResultAverage:
    def test_average_value_bpfs_suspend(self, bpfs_xml_results):
        avg = get_result_average(bpfs_xml_results, "FastStartup-Suspend-Overall-Time")
        assert avg == 6.0

    def test_average_value_bpfs_resume(self, bpfs_xml_results):
        avg = get_result_average(bpfs_xml_results, "FastStartup-Resume-Overall-Time")
        assert avg == 10.0

    def test_unknown_key_raises(self, bpfs_xml_results):
        with pytest.raises(ADKResultError):
            get_result_average(bpfs_xml_results, "NoSuchKey")


# ---------------------------------------------------------------------------
# get_result_hiberfile_read
# ---------------------------------------------------------------------------

class TestGetResultHiberfileRead:
    def test_returns_tuple(self, hiberfile_xml_results):
        avg_ms, avg_kb = get_result_hiberfile_read(
            hiberfile_xml_results, "FastStartup-Resume-ReadHiberFile"
        )
        assert isinstance(avg_ms, (int, float))
        assert isinstance(avg_kb, (int, float))

    def test_values_match_fixture(self, hiberfile_xml_results):
        avg_ms, avg_kb = get_result_hiberfile_read(
            hiberfile_xml_results, "FastStartup-Resume-ReadHiberFile"
        )
        assert avg_ms == 2
        assert avg_kb == 2048

    def test_unknown_key_raises(self, hiberfile_xml_results):
        with pytest.raises(ADKResultError):
            get_result_hiberfile_read(hiberfile_xml_results, "NoSuchKey")


# ---------------------------------------------------------------------------
# check_result_bpfs
# ---------------------------------------------------------------------------

class TestCheckResultBpfs:
    def test_suspend_and_resume_within_spec_passes(self, bpfs_xml_results):
        ok, msg = check_result_bpfs(bpfs_xml_results)
        assert ok is True

    def test_suspend_over_spec_fails(self, bpfs_xml_results_fail_suspend):
        ok, msg = check_result_bpfs(bpfs_xml_results_fail_suspend)
        assert ok is False
        assert "Suspend" in msg

    def test_custom_threshold_applied(self, bpfs_xml_results):
        # Lower threshold so 6s suspend now fails
        ok, msg = check_result_bpfs(
            bpfs_xml_results,
            thresholds={"FastStartup-Suspend-Overall-Time": 5,
                        "FastStartup-Resume-Overall-Time": 12}
        )
        assert ok is False


# ---------------------------------------------------------------------------
# check_result_standby
# ---------------------------------------------------------------------------

class TestCheckResultStandby:
    def test_within_spec_passes(self, standby_xml_results):
        ok, msg = check_result_standby(standby_xml_results)
        assert ok is True

    def test_custom_threshold_fails(self, standby_xml_results):
        # Reduce spec so 3s suspend now fails
        ok, msg = check_result_standby(
            standby_xml_results,
            thresholds={"Standby-Suspend-Overall-Time": 2,
                        "Standby-Resume-Overall-Time": 3}
        )
        assert ok is False


# ---------------------------------------------------------------------------
# check_result_hiberfile_read
# ---------------------------------------------------------------------------

class TestCheckResultHiberfileRead:
    def test_high_throughput_passes(self, hiberfile_xml_results):
        # Fixture: 2048 KB / 1024 = 2 MB in 2 ms = 1000 MB/s > 500 spec
        ok, msg = check_result_hiberfile_read(hiberfile_xml_results)
        assert ok is True

    def test_low_throughput_fails(self, hiberfile_xml_results):
        # Set spec above 1000 so it fails
        ok, msg = check_result_hiberfile_read(
            hiberfile_xml_results,
            thresholds={"FastStartup-Resume-ReadHiberFile": 2000}
        )
        assert ok is False
