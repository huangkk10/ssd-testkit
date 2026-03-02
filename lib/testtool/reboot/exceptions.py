"""
OsReboot Custom Exceptions

This module defines the custom exception hierarchy for OsReboot operations.
All exceptions inherit from OsRebootError base class.
"""


class OsRebootError(Exception):
    """Base exception for all OsReboot-related errors."""
    pass


class OsRebootConfigError(OsRebootError):
    """
    Configuration error.
    Raised when invalid config params are provided or required params are missing.
    """
    pass


class OsRebootTimeoutError(OsRebootError):
    """
    Timeout error.
    Raised when the shutdown command or reboot cycle exceeds the expected time.
    """
    pass


class OsRebootProcessError(OsRebootError):
    """
    Process control error.
    Raised when launching or aborting the shutdown.exe command fails
    (non-zero exit code or OS-level error).
    """
    pass


class OsRebootStateError(OsRebootError):
    """
    State persistence error.
    Raised when reading from or writing to the reboot state file fails.
    """
    pass


class OsRebootTestFailedError(OsRebootError):
    """
    Test failure error.
    Raised when the full reboot cycle sequence does not complete successfully.
    """
    pass
