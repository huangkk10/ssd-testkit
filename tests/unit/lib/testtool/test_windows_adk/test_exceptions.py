"""
Unit tests for windows_adk exceptions module.
"""

import pytest
from lib.testtool.windows_adk.exceptions import (
    ADKConfigError,
    ADKError,
    ADKProcessError,
    ADKResultError,
    ADKTimeoutError,
    ADKUIError,
)


class TestExceptions:
    def test_adk_error_inherits_exception(self):
        assert issubclass(ADKError, Exception)

    def test_all_errors_inherit_adk_error(self):
        for cls in (ADKConfigError, ADKUIError, ADKResultError, ADKTimeoutError, ADKProcessError):
            assert issubclass(cls, ADKError), f"{cls.__name__} should inherit ADKError"

    def test_adk_ui_error_message(self):
        exc = ADKUIError("window not found")
        assert "window not found" in str(exc)

    def test_adk_result_error_message(self):
        exc = ADKResultError("result missing")
        assert "result missing" in str(exc)

    def test_adk_timeout_error_message(self):
        exc = ADKTimeoutError("timed out after 60s")
        assert "60s" in str(exc)

    def test_adk_process_error_message(self):
        exc = ADKProcessError("axe.exe not found")
        assert "axe.exe" in str(exc)

    def test_raise_and_catch_as_base(self):
        with pytest.raises(ADKError):
            raise ADKUIError("test")
