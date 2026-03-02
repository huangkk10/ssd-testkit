"""
PwrTest Custom Exceptions

This module defines custom exception classes for PwrTest operations.
All exceptions inherit from PwrTestError base class.
"""


class PwrTestError(Exception):
    """Base exception for all PwrTest-related errors."""
    pass


class PwrTestConfigError(PwrTestError):
    """
    Configuration error.
    Raised when invalid config params are provided or required params are missing.
    """
    pass


class PwrTestTimeoutError(PwrTestError):
    """
    Timeout error.
    Raised when PwrTest execution exceeds the configured timeout limit.
    """
    pass


class PwrTestProcessError(PwrTestError):
    """
    Process control error.
    Raised when starting, stopping, or monitoring the pwrtest.exe process fails.
    """
    pass


class PwrTestLogParseError(PwrTestError):
    """
    Log parse error.
    Raised when parsing pwrtestlog.log or pwrtestlog.xml fails
    (file missing, empty, or unrecognised format).
    """
    pass


class PwrTestTestFailedError(PwrTestError):
    """
    Test failure error.
    Raised when pwrtest.exe itself reports a FAIL result.
    """
    pass
