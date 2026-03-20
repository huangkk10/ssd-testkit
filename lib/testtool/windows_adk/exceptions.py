"""
Windows ADK Custom Exceptions

All exceptions inherit from ADKError base class.
"""


class ADKError(Exception):
    """Base exception for all Windows ADK errors."""
    pass


class ADKConfigError(ADKError):
    """Raised when configuration is invalid or missing."""
    pass


class ADKUIError(ADKError):
    """Raised when a pywinauto UI operation fails (window not found, timeout, etc.)."""
    pass


class ADKResultError(ADKError):
    """Raised when the assessment result is missing, unreadable, or fails spec check."""
    pass


class ADKTimeoutError(ADKError):
    """Raised when an operation exceeds the allowed timeout."""
    pass


class ADKProcessError(ADKError):
    """Raised when a process operation (kill, connect) fails."""
    pass
