"""
SmiCli Custom Exceptions

This module defines custom exception classes for SmiCli operations.
All exceptions inherit from SmiCliError base class.
"""


class SmiCliError(Exception):
    """
    Base exception class for all SmiCli-related errors.

    Catch this to handle any SmiCli-related error.
    """
    pass


class SmiCliConfigError(SmiCliError):
    """
    Configuration error exception.

    Raised when:
    - Invalid configuration parameters are provided
    - Required parameters are missing
    - Parameter values are out of acceptable ranges

    Example:
        >>> raise SmiCliConfigError("Invalid timeout_seconds value: -1")
    """
    pass


class SmiCliTimeoutError(SmiCliError):
    """
    Timeout error exception.

    Raised when SmiCli2.exe execution exceeds the configured timeout.

    Example:
        >>> raise SmiCliTimeoutError("SmiCli2.exe timed out after 60 seconds")
    """
    pass


class SmiCliProcessError(SmiCliError):
    """
    Process control error exception.

    Raised when:
    - SmiCli2.exe executable is not found
    - Subprocess fails to launch
    - SmiCli2.exe returns a non-zero exit code

    Example:
        >>> raise SmiCliProcessError("SmiCli2.exe returned exit code 1")
    """
    pass


class SmiCliTestFailedError(SmiCliError):
    """
    Test failure error exception.

    Raised when the output file produced by SmiCli2.exe is missing,
    empty, or does not contain the expected ``[info]`` / ``[disk_*]`` sections.

    Example:
        >>> raise SmiCliTestFailedError("Output file format is abnormal")
    """
    pass
