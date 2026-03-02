"""
Unit tests for PwrTest exceptions module.
"""

import pytest
from lib.testtool.pwrtest.exceptions import (
    PwrTestError,
    PwrTestConfigError,
    PwrTestTimeoutError,
    PwrTestProcessError,
    PwrTestLogParseError,
    PwrTestTestFailedError,
)


class TestPwrTestExceptions:
    """Test suite for PwrTest exception classes."""

    def test_base_exception_raised(self):
        with pytest.raises(PwrTestError):
            raise PwrTestError("Base error")

    def test_base_exception_message(self):
        try:
            raise PwrTestError("test message")
        except PwrTestError as e:
            assert str(e) == "test message"

    # ---- ConfigError ----

    def test_config_error_raised(self):
        with pytest.raises(PwrTestConfigError):
            raise PwrTestConfigError("bad config")

    def test_config_error_inherits_base(self):
        with pytest.raises(PwrTestError):
            raise PwrTestConfigError("bad config")

    # ---- TimeoutError ----

    def test_timeout_error_raised(self):
        with pytest.raises(PwrTestTimeoutError):
            raise PwrTestTimeoutError("timed out")

    def test_timeout_error_inherits_base(self):
        with pytest.raises(PwrTestError):
            raise PwrTestTimeoutError("timed out")

    # ---- ProcessError ----

    def test_process_error_raised(self):
        with pytest.raises(PwrTestProcessError):
            raise PwrTestProcessError("process failed")

    def test_process_error_inherits_base(self):
        with pytest.raises(PwrTestError):
            raise PwrTestProcessError("process failed")

    # ---- LogParseError ----

    def test_log_parse_error_raised(self):
        with pytest.raises(PwrTestLogParseError):
            raise PwrTestLogParseError("parse failed")

    def test_log_parse_error_inherits_base(self):
        with pytest.raises(PwrTestError):
            raise PwrTestLogParseError("parse failed")

    # ---- TestFailedError ----

    def test_test_failed_error_raised(self):
        with pytest.raises(PwrTestTestFailedError):
            raise PwrTestTestFailedError("test failed")

    def test_test_failed_error_inherits_base(self):
        with pytest.raises(PwrTestError):
            raise PwrTestTestFailedError("test failed")

    # ---- Hierarchy / isinstance checks ----

    def test_exception_hierarchy(self):
        """All sub-exceptions must inherit from PwrTestError and Exception."""
        sub_classes = [
            PwrTestConfigError,
            PwrTestTimeoutError,
            PwrTestProcessError,
            PwrTestLogParseError,
            PwrTestTestFailedError,
        ]
        for exc_class in sub_classes:
            assert issubclass(exc_class, PwrTestError)
            assert issubclass(exc_class, Exception)

    def test_exception_with_rich_message(self):
        msg = "param='os_name', value='winXP', reason='not in known set'"
        try:
            raise PwrTestConfigError(msg)
        except PwrTestConfigError as e:
            assert "os_name" in str(e)
            assert "winXP" in str(e)
