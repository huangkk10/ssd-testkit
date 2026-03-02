"""
Unit tests for lib.testtool.osconfig.exceptions
"""

import pytest
from lib.testtool.osconfig.exceptions import (
    OsConfigError,
    OsConfigPermissionError,
    OsConfigNotSupportedError,
    OsConfigTimeoutError,
    OsConfigStateError,
    OsConfigActionError,
)


class TestOsConfigExceptionHierarchy:
    """All custom exceptions must inherit from OsConfigError."""

    @pytest.mark.parametrize("exc_class", [
        OsConfigPermissionError,
        OsConfigNotSupportedError,
        OsConfigTimeoutError,
        OsConfigStateError,
        OsConfigActionError,
    ])
    def test_inherits_from_base(self, exc_class):
        assert issubclass(exc_class, OsConfigError)

    @pytest.mark.parametrize("exc_class", [
        OsConfigError,
        OsConfigPermissionError,
        OsConfigNotSupportedError,
        OsConfigTimeoutError,
        OsConfigStateError,
        OsConfigActionError,
    ])
    def test_inherits_from_exception(self, exc_class):
        assert issubclass(exc_class, Exception)


class TestOsConfigErrorCanBeRaised:
    """Each exception class can be raised and caught."""

    def test_base_error(self):
        with pytest.raises(OsConfigError, match="base error"):
            raise OsConfigError("base error")

    def test_permission_error(self):
        with pytest.raises(OsConfigPermissionError):
            raise OsConfigPermissionError("access denied")

    def test_permission_error_caught_as_base(self):
        with pytest.raises(OsConfigError):
            raise OsConfigPermissionError("access denied")

    def test_not_supported_error(self):
        with pytest.raises(OsConfigNotSupportedError):
            raise OsConfigNotSupportedError("build too old")

    def test_not_supported_error_caught_as_base(self):
        with pytest.raises(OsConfigError):
            raise OsConfigNotSupportedError("build too old")

    def test_timeout_error(self):
        with pytest.raises(OsConfigTimeoutError):
            raise OsConfigTimeoutError("timed out")

    def test_timeout_error_caught_as_base(self):
        with pytest.raises(OsConfigError):
            raise OsConfigTimeoutError("timed out")

    def test_state_error(self):
        with pytest.raises(OsConfigStateError):
            raise OsConfigStateError("state file missing")

    def test_state_error_caught_as_base(self):
        with pytest.raises(OsConfigError):
            raise OsConfigStateError("state file missing")

    def test_action_error(self):
        with pytest.raises(OsConfigActionError):
            raise OsConfigActionError("action failed")

    def test_action_error_caught_as_base(self):
        with pytest.raises(OsConfigError):
            raise OsConfigActionError("action failed")


class TestOsConfigErrorMessages:
    """Exception messages are preserved."""

    @pytest.mark.parametrize("exc_class, message", [
        (OsConfigError, "test message"),
        (OsConfigPermissionError, "access denied to HKLM\\..."),
        (OsConfigNotSupportedError, "feature requires Build >= 14393"),
        (OsConfigTimeoutError, "WSearch did not stop within 30s"),
        (OsConfigStateError, "failed to load snapshot.json"),
        (OsConfigActionError, "sc.exe returned rc=1"),
    ])
    def test_message_preserved(self, exc_class, message):
        try:
            raise exc_class(message)
        except exc_class as e:
            assert str(e) == message
