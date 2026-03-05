"""
SleepStudy Custom Exceptions

Exception hierarchy for the ``lib.testtool.sleepstudy`` package, which
wraps Windows ``powercfg /sleepstudy`` and its HTML report parser.

All exceptions inherit from :class:`SleepStudyError`.
"""


class SleepStudyError(Exception):
    """
    Base exception for all SleepStudy-related errors.

    Catch this to handle any error raised by the sleepstudy package.

    Example:
        >>> try:
        ...     # sleepstudy operations
        ...     pass
        ... except SleepStudyError as e:
        ...     print(f"SleepStudy error: {e}")
    """
    pass


class SleepStudyConfigError(SleepStudyError):
    """
    Configuration error.

    Raised when:
    - Invalid configuration parameters are provided
    - Required parameters are missing
    - Parameter values are of wrong type or out of range

    Example:
        >>> raise SleepStudyConfigError("Invalid timeout value: -1")
    """
    pass


class SleepStudyTimeoutError(SleepStudyError):
    """
    Timeout error.

    Raised when ``powercfg /sleepstudy`` does not complete within the
    configured timeout.

    Example:
        >>> raise SleepStudyTimeoutError("powercfg /sleepstudy timed out after 60s")
    """
    pass


class SleepStudyProcessError(SleepStudyError):
    """
    Process error.

    Raised when:
    - ``powercfg.exe`` fails to start
    - ``powercfg /sleepstudy`` returns a non-zero exit code
    - The process terminates unexpectedly

    Example:
        >>> raise SleepStudyProcessError("powercfg /sleepstudy exited with code 1")
    """
    pass


class SleepStudyLogParseError(SleepStudyError):
    """
    HTML report parse error.

    Raised when:
    - The ``sleepstudy-report.html`` file is missing or unreadable
    - The ``LocalSprData`` JSON payload is not found in the HTML
    - The JSON structure does not match the expected Sleep Study format
    - An invalid date/time filter argument is provided

    Example:
        >>> raise SleepStudyLogParseError(
        ...     "LocalSprData not found in sleepstudy-report.html"
        ... )
    """
    pass


class SleepStudyTestFailedError(SleepStudyError):
    """
    Test failure error.

    Raised when a SleepStudy test run is considered failed (e.g. no sleep
    sessions were recorded, or SW DRIPS fell below threshold).

    Example:
        >>> raise SleepStudyTestFailedError("SW DRIPS 45% below threshold 85%")
    """
    pass
