"""
CDI (CrystalDiskInfo) Custom Exceptions

This module defines custom exception classes for CDI operations.
All exceptions inherit from CDIError base class.
"""


class CDIError(Exception):
    """Base exception for all CDI-related errors."""
    pass


class CDIConfigError(CDIError):
    """
    Configuration error.
    Raised when invalid config params are provided or required params are missing.
    """
    pass


class CDITimeoutError(CDIError):
    """
    Timeout error.
    Raised when CDI execution exceeds the configured timeout limit.
    """
    pass


class CDIProcessError(CDIError):
    """
    Process control error.
    Raised when starting, stopping, or monitoring the DiskInfo64.exe process fails.
    """
    pass


class CDIUIError(CDIError):
    """
    UI interaction error.
    Raised when pywinauto cannot connect to or interact with the CrystalDiskInfo window.
    """
    pass


class CDITestFailedError(CDIError):
    """
    Test failure error.
    Raised when SMART value comparison or disk health checks fail.
    """
    pass
