"""
WinPVT Custom Exceptions

Exception hierarchy for WinPVT test operations.
All exceptions inherit from WinPVTError.
"""


class WinPVTError(Exception):
    """Base exception for all WinPVT-related errors."""


class WinPVTConfigError(WinPVTError):
    """Raised when configuration is missing or invalid."""


class WinPVTTimeoutError(WinPVTError):
    """Raised when WinPVT execution exceeds the allowed timeout."""


class WinPVTProcessError(WinPVTError):
    """Raised when the WinPVT process cannot be started or monitored."""


class WinPVTUIError(WinPVTError):
    """Raised when UI automation fails (pywinauto errors)."""


class WinPVTTestFailedError(WinPVTError):
    """Raised when WinPVT reports a test failure in its results."""
