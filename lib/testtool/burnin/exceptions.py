"""
BurnIN Custom Exceptions

This module defines custom exception classes for BurnIN operations.
All exceptions inherit from BurnInError base class.
"""


class BurnInError(Exception):
    """
    Base exception class for all BurnIN-related errors.
    
    This is the parent class for all BurnIN exceptions.
    Catch this to handle any BurnIN-related error.
    
    Example:
        >>> try:
        ...     # BurnIN operations
        ...     pass
        ... except BurnInError as e:
        ...     print(f"BurnIN error occurred: {e}")
    """
    pass


class BurnInConfigError(BurnInError):
    """
    Configuration error exception.
    
    Raised when:
    - Invalid configuration parameters are provided
    - Configuration file is missing or malformed
    - Required parameters are not set
    - Parameter values are out of acceptable ranges
    
    Example:
        >>> raise BurnInConfigError("Invalid total_time value: -1")
    """
    pass


class BurnInTimeoutError(BurnInError):
    """
    Timeout error exception.
    
    Raised when:
    - BurnIN test execution exceeds timeout limit
    - Process startup timeout
    - UI connection timeout
    
    Example:
        >>> raise BurnInTimeoutError("Test execution timeout after 3600 seconds")
    """
    pass


class BurnInProcessError(BurnInError):
    """
    Process control error exception.
    
    Raised when:
    - BurnIN process fails to start
    - Process termination fails
    - Process communication errors
    - Process not found
    
    Example:
        >>> raise BurnInProcessError("Failed to start BurnIN executable")
    """
    pass


class BurnInInstallError(BurnInError):
    """
    Installation/Uninstallation error exception.
    
    Raised when:
    - Installation fails
    - Uninstallation fails
    - Installer not found
    - License file issues
    
    Example:
        >>> raise BurnInInstallError("Installation failed: Installer returned code 1")
    """
    pass


class BurnInUIError(BurnInError):
    """
    UI interaction error exception.
    
    Raised when:
    - Failed to connect to BurnIN window
    - UI element not found
    - Window state errors
    - pywinauto errors
    
    Example:
        >>> raise BurnInUIError("Failed to connect to BurnIN window after 60 retries")
    """
    pass


class BurnInTestFailedError(BurnInError):
    """
    Test execution failed exception.
    
    Raised when:
    - BurnIN test fails
    - Errors detected during test execution
    - Test completed with failure status
    
    Example:
        >>> raise BurnInTestFailedError("BurnIN test failed with 5 errors")
    """
    pass
