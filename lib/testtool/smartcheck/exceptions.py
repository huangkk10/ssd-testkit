"""
SmartCheck Custom Exceptions

This module defines custom exception classes for SmartCheck operations.
All exceptions inherit from SmartCheckError base class.
"""


class SmartCheckError(Exception):
    """
    Base exception class for all SmartCheck-related errors.
    
    This is the parent class for all SmartCheck exceptions.
    Catch this to handle any SmartCheck-related error.
    """
    pass


class SmartCheckConfigError(SmartCheckError):
    """
    Configuration error exception.
    
    Raised when:
    - Invalid configuration parameters are provided
    - Configuration file is missing or malformed
    - Required parameters are not set
    
    Example:
        >>> raise SmartCheckConfigError("Invalid total_time value: -1")
    """
    pass


class SmartCheckTimeoutError(SmartCheckError):
    """
    Timeout error exception.
    
    Raised when:
    - SmartCheck.bat execution exceeds timeout limit
    - RunCard.ini monitoring times out
    - Process startup timeout
    
    Example:
        >>> raise SmartCheckTimeoutError("Execution timeout after 3600 seconds")
    """
    pass


class SmartCheckProcessError(SmartCheckError):
    """
    Process control error exception.
    
    Raised when:
    - SmartCheck.bat fails to start
    - Process termination fails
    - Process communication errors
    
    Example:
        >>> raise SmartCheckProcessError("Failed to start SmartCheck.bat")
    """
    pass


class SmartCheckRunCardError(SmartCheckError):
    """
    RunCard.ini related error exception.
    
    Raised when:
    - RunCard.ini not found in expected location
    - RunCard.ini format is invalid
    - Failed to read RunCard.ini status
    
    Example:
        >>> raise SmartCheckRunCardError("RunCard.ini not found in output directory")
    """
    pass
