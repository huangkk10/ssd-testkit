"""
Unit tests for CDI exceptions module.
"""

import pytest
from lib.testtool.cdi.exceptions import (
    CDIError,
    CDIConfigError,
    CDITimeoutError,
    CDIProcessError,
    CDIUIError,
    CDITestFailedError,
)


class TestCDIExceptions:
    """Test suite for CDI exception classes."""

    def test_base_exception_raised(self):
        with pytest.raises(CDIError):
            raise CDIError("base error")

    def test_base_exception_message(self):
        try:
            raise CDIError("base message")
        except CDIError as e:
            assert str(e) == "base message"

    def test_config_error_raised(self):
        with pytest.raises(CDIConfigError):
            raise CDIConfigError("bad config")

    def test_config_error_inherits_base(self):
        with pytest.raises(CDIError):
            raise CDIConfigError("bad config")

    def test_timeout_error_raised(self):
        with pytest.raises(CDITimeoutError):
            raise CDITimeoutError("timed out")

    def test_timeout_error_inherits_base(self):
        with pytest.raises(CDIError):
            raise CDITimeoutError("timed out")

    def test_process_error_raised(self):
        with pytest.raises(CDIProcessError):
            raise CDIProcessError("process failed")

    def test_process_error_inherits_base(self):
        with pytest.raises(CDIError):
            raise CDIProcessError("process failed")

    def test_ui_error_raised(self):
        with pytest.raises(CDIUIError):
            raise CDIUIError("UI not found")

    def test_ui_error_inherits_base(self):
        with pytest.raises(CDIError):
            raise CDIUIError("UI not found")

    def test_test_failed_error_raised(self):
        with pytest.raises(CDITestFailedError):
            raise CDITestFailedError("test failed")

    def test_test_failed_error_inherits_base(self):
        with pytest.raises(CDIError):
            raise CDITestFailedError("test failed")

    def test_all_subclasses_inherit_exception(self):
        for klass in (CDIConfigError, CDITimeoutError, CDIProcessError,
                      CDIUIError, CDITestFailedError):
            assert issubclass(klass, CDIError)
            assert issubclass(klass, Exception)

    def test_exception_message_preserved(self):
        msg = "param='drive_letter', value='Z:', reason='not found'"
        try:
            raise CDIConfigError(msg)
        except CDIConfigError as e:
            assert "drive_letter" in str(e)
            assert "not found" in str(e)
