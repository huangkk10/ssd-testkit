"""
Diskercise Custom Exceptions

This module defines custom exception classes for Diskercise operations.
All exceptions inherit from DiskerciseError base class.
"""


class DiskerciseError(Exception):
    """Base exception for all Diskercise-related errors."""
    pass


class DiskerciseConfigError(DiskerciseError):
    """
    Configuration error.
    Raised when invalid config params are provided or required params are missing.
    """
    pass


class DiskerciseTimeoutError(DiskerciseError):
    """
    Timeout error.
    Raised when Diskercise execution exceeds the configured timeout limit.
    """
    pass


class DiskerciseProcessError(DiskerciseError):
    """
    Process control error.
    Raised when starting, stopping, or monitoring the Diskercise process fails.
    """
    pass


class DiskerciseUIError(DiskerciseError):
    """
    UI interaction error.
    Raised when pywinauto cannot connect to or interact with the Diskercise window.
    """
    pass


class DiskerciseTestFailedError(DiskerciseError):
    """
    Test failure error.
    Raised when Diskercise reports an Operation Failure dialog or scan error.
    """
    pass
