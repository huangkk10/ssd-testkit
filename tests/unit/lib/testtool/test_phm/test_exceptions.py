"""
Unit tests for PHM exceptions module.
"""

import pytest
from lib.testtool.phm.exceptions import (
    PHMError,
    PHMConfigError,
    PHMTimeoutError,
    PHMProcessError,
    PHMInstallError,
    PHMUIError,
    PHMLogParseError,
    PHMTestFailedError,
)


class TestPHMExceptions:
    """Test suite for PHM exception classes."""

    def test_base_exception_raised(self):
        with pytest.raises(PHMError):
            raise PHMError("Base error")

    def test_base_exception_message(self):
        try:
            raise PHMError("test message")
        except PHMError as exc:
            assert str(exc) == "test message"

    # --- PHMConfigError ---

    def test_config_error_raised(self):
        with pytest.raises(PHMConfigError):
            raise PHMConfigError("bad config")

    def test_config_error_inherits_base(self):
        with pytest.raises(PHMError):
            raise PHMConfigError("bad config")

    # --- PHMTimeoutError ---

    def test_timeout_error_raised(self):
        with pytest.raises(PHMTimeoutError):
            raise PHMTimeoutError("timed out")

    def test_timeout_error_inherits_base(self):
        with pytest.raises(PHMError):
            raise PHMTimeoutError("timed out")

    # --- PHMProcessError ---

    def test_process_error_raised(self):
        with pytest.raises(PHMProcessError):
            raise PHMProcessError("process failed")

    def test_process_error_inherits_base(self):
        with pytest.raises(PHMError):
            raise PHMProcessError("process failed")

    # --- PHMInstallError ---

    def test_install_error_raised(self):
        with pytest.raises(PHMInstallError):
            raise PHMInstallError("install failed")

    def test_install_error_inherits_base(self):
        with pytest.raises(PHMError):
            raise PHMInstallError("install failed")

    # --- PHMUIError ---

    def test_ui_error_raised(self):
        with pytest.raises(PHMUIError):
            raise PHMUIError("window not found")

    def test_ui_error_inherits_base(self):
        with pytest.raises(PHMError):
            raise PHMUIError("window not found")

    # --- PHMLogParseError ---

    def test_log_parse_error_raised(self):
        with pytest.raises(PHMLogParseError):
            raise PHMLogParseError("parse failed")

    def test_log_parse_error_inherits_base(self):
        with pytest.raises(PHMError):
            raise PHMLogParseError("parse failed")

    # --- PHMTestFailedError ---

    def test_test_failed_error_raised(self):
        with pytest.raises(PHMTestFailedError):
            raise PHMTestFailedError("test failed")

    def test_test_failed_error_inherits_base(self):
        with pytest.raises(PHMError):
            raise PHMTestFailedError("test failed")

    # --- Hierarchy ---

    def test_all_inherit_from_phm_error(self):
        sub_classes = [
            PHMConfigError,
            PHMTimeoutError,
            PHMProcessError,
            PHMInstallError,
            PHMUIError,
            PHMLogParseError,
            PHMTestFailedError,
        ]
        for cls in sub_classes:
            assert issubclass(cls, PHMError), f"{cls.__name__} must inherit PHMError"
            assert issubclass(cls, Exception), f"{cls.__name__} must inherit Exception"

    def test_all_inherit_from_exception(self):
        assert issubclass(PHMError, Exception)

    def test_exception_message_preserved(self):
        msg = "detailed error: param='cycle_count', value=-1"
        try:
            raise PHMConfigError(msg)
        except PHMConfigError as exc:
            assert "cycle_count" in str(exc)
            assert "-1" in str(exc)
