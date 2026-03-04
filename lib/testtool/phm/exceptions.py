"""
PHM (Powerhouse Mountain) Custom Exceptions

This module defines custom exception classes for PHM operations.
All exceptions inherit from PHMError base class.
"""


class PHMError(Exception):
    """
    Base exception class for all PHM-related errors.

    Catch this to handle any PHM-related error.

    Example:
        >>> try:
        ...     # PHM operations
        ...     pass
        ... except PHMError as e:
        ...     print(f"PHM error occurred: {e}")
    """
    pass


class PHMConfigError(PHMError):
    """
    Configuration error exception.

    Raised when:
    - Invalid configuration parameters are provided
    - Required parameters are not set
    - Parameter values are invalid types or out of range

    Example:
        >>> raise PHMConfigError("Invalid cycle_count value: -1")
    """
    pass


class PHMTimeoutError(PHMError):
    """
    Timeout error exception.

    Raised when:
    - PHM test execution exceeds the configured timeout limit
    - Process startup timeout
    - UI connection timeout

    Example:
        >>> raise PHMTimeoutError("Test execution timeout after 3600 seconds")
    """
    pass


class PHMProcessError(PHMError):
    """
    Process control error exception.

    Raised when:
    - PHM process fails to start
    - Process terminates unexpectedly
    - Process monitoring fails

    Example:
        >>> raise PHMProcessError("Failed to start PHM process")
    """
    pass


class PHMInstallError(PHMError):
    """
    Installation error exception.

    Raised when:
    - PHM installation fails
    - Installer executable not found
    - Uninstallation fails
    - Installation verification fails

    Example:
        >>> raise PHMInstallError("Installer not found: phm_nda_V4.22.0.exe")
    """
    pass


class PHMUIError(PHMError):
    """
    UI interaction error exception.

    Raised when:
    - pywinauto cannot connect to the PHM window
    - Expected UI control is not found
    - UI operation (click, type) fails

    Example:
        >>> raise PHMUIError("Could not find 'Start Test' button")
    """
    pass


class PHMLogParseError(PHMError):
    """
    HTML log parsing error exception.

    Raised when:
    - HTML report file not found or unreadable
    - HTML structure does not match expected format
    - Required fields are missing from the report

    Example:
        >>> raise PHMLogParseError("Expected result table not found in HTML")
    """
    pass


class PHMTestFailedError(PHMError):
    """
    Test failure error exception.

    Raised when the PHM test itself reports a FAIL result.

    Example:
        >>> raise PHMTestFailedError("PHM reported FAIL: 2 errors detected")
    """
    pass


class PHMSleepReportParseError(PHMLogParseError):
    """
    Sleep Study report parsing error.

    Raised when:
    - The ``sleepstudy-report.html`` file is missing or unreadable
    - The ``LocalSprData`` JSON payload is not found in the HTML
    - The JSON structure does not match the expected Sleep Study format
    - An invalid date/time filter argument is provided

    This is a sub-class of :class:`PHMLogParseError` so existing callers
    that catch ``PHMLogParseError`` will also catch this error.

    Example:
        >>> raise PHMSleepReportParseError(
        ...     "LocalSprData not found in sleepstudy-report.html"
        ... )
    """
    pass
