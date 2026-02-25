"""
Unit tests for PythonInstaller exceptions module.
"""

import pytest
from lib.testtool.python_installer.exceptions import (
    PythonInstallerError,
    PythonInstallerConfigError,
    PythonInstallerTimeoutError,
    PythonInstallerProcessError,
    PythonInstallerInstallError,
    PythonInstallerVersionError,
    PythonInstallerTestFailedError,
)


class TestPythonInstallerExceptions:
    """Test suite for PythonInstaller exception classes."""

    # ----- Base exception -----

    def test_base_exception_raised(self):
        with pytest.raises(PythonInstallerError):
            raise PythonInstallerError("Base error")

    def test_base_exception_message(self):
        try:
            raise PythonInstallerError("Test message")
        except PythonInstallerError as exc:
            assert str(exc) == "Test message"

    # ----- Config error -----

    def test_config_error_raised(self):
        with pytest.raises(PythonInstallerConfigError):
            raise PythonInstallerConfigError("bad config")

    def test_config_error_inherits_base(self):
        with pytest.raises(PythonInstallerError):
            raise PythonInstallerConfigError("bad config")

    # ----- Timeout error -----

    def test_timeout_error_raised(self):
        with pytest.raises(PythonInstallerTimeoutError):
            raise PythonInstallerTimeoutError("timed out")

    def test_timeout_error_inherits_base(self):
        with pytest.raises(PythonInstallerError):
            raise PythonInstallerTimeoutError("timed out")

    # ----- Process error -----

    def test_process_error_raised(self):
        with pytest.raises(PythonInstallerProcessError):
            raise PythonInstallerProcessError("process failed")

    def test_process_error_inherits_base(self):
        with pytest.raises(PythonInstallerError):
            raise PythonInstallerProcessError("process failed")

    # ----- Install error -----

    def test_install_error_raised(self):
        with pytest.raises(PythonInstallerInstallError):
            raise PythonInstallerInstallError("install failed")

    def test_install_error_inherits_base(self):
        with pytest.raises(PythonInstallerError):
            raise PythonInstallerInstallError("install failed")

    # ----- Version error -----

    def test_version_error_raised(self):
        with pytest.raises(PythonInstallerVersionError):
            raise PythonInstallerVersionError("bad version")

    def test_version_error_inherits_base(self):
        with pytest.raises(PythonInstallerError):
            raise PythonInstallerVersionError("bad version")

    # ----- Test failed error -----

    def test_test_failed_error_raised(self):
        with pytest.raises(PythonInstallerTestFailedError):
            raise PythonInstallerTestFailedError("verification failed")

    def test_test_failed_error_inherits_base(self):
        with pytest.raises(PythonInstallerError):
            raise PythonInstallerTestFailedError("verification failed")

    # ----- Hierarchy -----

    def test_all_inherit_from_base(self):
        sub_classes = [
            PythonInstallerConfigError,
            PythonInstallerTimeoutError,
            PythonInstallerProcessError,
            PythonInstallerInstallError,
            PythonInstallerVersionError,
            PythonInstallerTestFailedError,
        ]
        for exc_class in sub_classes:
            assert issubclass(exc_class, PythonInstallerError), (
                f"{exc_class.__name__} does not inherit from PythonInstallerError"
            )
            assert issubclass(exc_class, Exception)

    def test_exception_message_preserved(self):
        msg = "version='3.99', reason='unsupported major'"
        try:
            raise PythonInstallerVersionError(msg)
        except PythonInstallerVersionError as exc:
            assert "3.99" in str(exc)
            assert "unsupported" in str(exc)
