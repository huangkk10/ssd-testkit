"""
PythonInstaller Custom Exceptions

This module defines custom exception classes for PythonInstaller operations.
All exceptions inherit from PythonInstallerError base class.
"""


class PythonInstallerError(Exception):
    """Base exception for all PythonInstaller-related errors."""
    pass


class PythonInstallerConfigError(PythonInstallerError):
    """
    Configuration error.
    Raised when invalid config params are provided or required params are missing.
    """
    pass


class PythonInstallerTimeoutError(PythonInstallerError):
    """
    Timeout error.
    Raised when PythonInstaller execution exceeds the configured timeout limit.
    """
    pass


class PythonInstallerProcessError(PythonInstallerError):
    """
    Process control error.
    Raised when starting, stopping, or monitoring the installer process fails.
    """
    pass


class PythonInstallerInstallError(PythonInstallerError):
    """
    Installation error.
    Raised when Python installation or uninstallation fails.
    """
    pass


class PythonInstallerVersionError(PythonInstallerError):
    """
    Version error.
    Raised when the specified Python version is invalid, unsupported, or not found.
    """
    pass


class PythonInstallerTestFailedError(PythonInstallerError):
    """
    Test failure error.
    Raised when the installation verification fails.
    """
    pass
