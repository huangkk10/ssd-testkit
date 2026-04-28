"""
Unit tests for Diskercise exceptions module.
"""

import pytest
from lib.testtool.diskercise.exceptions import (
    DiskerciseError,
    DiskerciseConfigError,
    DiskerciseTimeoutError,
    DiskerciseProcessError,
    DiskerciseUIError,
    DiskerciseTestFailedError,
)


class TestDiskerciseExceptions:
    """Test suite for Diskercise exception classes."""

    def test_base_exception_raised(self):
        with pytest.raises(DiskerciseError):
            raise DiskerciseError("Base error")

    def test_base_exception_message(self):
        try:
            raise DiskerciseError("test message")
        except DiskerciseError as e:
            assert str(e) == "test message"

    def test_config_error_raised(self):
        with pytest.raises(DiskerciseConfigError):
            raise DiskerciseConfigError("bad config")

    def test_config_error_inherits_base(self):
        with pytest.raises(DiskerciseError):
            raise DiskerciseConfigError("bad config")

    def test_timeout_error_raised(self):
        with pytest.raises(DiskerciseTimeoutError):
            raise DiskerciseTimeoutError("timed out")

    def test_timeout_error_inherits_base(self):
        with pytest.raises(DiskerciseError):
            raise DiskerciseTimeoutError("timed out")

    def test_process_error_raised(self):
        with pytest.raises(DiskerciseProcessError):
            raise DiskerciseProcessError("process failed")

    def test_process_error_inherits_base(self):
        with pytest.raises(DiskerciseError):
            raise DiskerciseProcessError("process failed")

    def test_ui_error_raised(self):
        with pytest.raises(DiskerciseUIError):
            raise DiskerciseUIError("ui failed")

    def test_ui_error_inherits_base(self):
        with pytest.raises(DiskerciseError):
            raise DiskerciseUIError("ui failed")

    def test_test_failed_error_raised(self):
        with pytest.raises(DiskerciseTestFailedError):
            raise DiskerciseTestFailedError("test failed")

    def test_test_failed_error_inherits_base(self):
        with pytest.raises(DiskerciseError):
            raise DiskerciseTestFailedError("test failed")

    def test_exception_hierarchy(self):
        """All exceptions must inherit from DiskerciseError and Exception."""
        sub_classes = [
            DiskerciseConfigError,
            DiskerciseTimeoutError,
            DiskerciseProcessError,
            DiskerciseUIError,
            DiskerciseTestFailedError,
        ]
        for exc_class in sub_classes:
            assert issubclass(exc_class, DiskerciseError)
            assert issubclass(exc_class, Exception)

    def test_exception_with_detailed_message(self):
        msg = "param='thread_count', value=-1, reason='must be >= 1'"
        try:
            raise DiskerciseConfigError(msg)
        except DiskerciseConfigError as e:
            assert "thread_count" in str(e)
            assert "-1" in str(e)
