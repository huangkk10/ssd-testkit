"""
OsConfig Custom Exceptions

This module defines custom exception classes for OsConfig operations.
All exceptions inherit from OsConfigError base class.

Hierarchy::

    OsConfigError
    ├── OsConfigPermissionError   # registry/service write denied (e.g. UAC, Tamper Protection)
    ├── OsConfigNotSupportedError # feature not available on this OS build/edition
    ├── OsConfigTimeoutError      # operation exceeded time limit
    ├── OsConfigStateError        # snapshot / revert JSON read-write failure
    └── OsConfigActionError       # generic failure inside a single Action
"""


class OsConfigError(Exception):
    """
    Base exception for all OsConfig-related errors.

    Catch this to handle any OsConfig-related error regardless of sub-type.

    Example::

        try:
            controller.apply()
        except OsConfigError as e:
            print(f"OsConfig error: {e}")
    """
    pass


class OsConfigPermissionError(OsConfigError):
    """
    Permission / access-denied error.

    Raised when:
    - A registry write is blocked (e.g. Tamper Protection, UAC)
    - A service control operation is denied
    - The process is not running as Administrator

    Example::

        raise OsConfigPermissionError(
            "Registry write to HKLM\\...\\Windows Defender blocked by Tamper Protection"
        )
    """
    pass


class OsConfigNotSupportedError(OsConfigError):
    """
    Feature-not-supported error.

    Raised when an action is not applicable on the current OS build or edition
    and ``fail_on_unsupported=True`` is set in the profile.
    When ``fail_on_unsupported=False`` (default), the action is silently
    skipped with a warning log instead of raising.

    Example::

        raise OsConfigNotSupportedError(
            "OneDrive metered-sync setting requires Build >= 14393 (RS1); "
            "current build: 10240"
        )
    """
    pass


class OsConfigTimeoutError(OsConfigError):
    """
    Operation timeout error.

    Raised when a service stop / start operation does not complete within
    the expected time window.

    Example::

        raise OsConfigTimeoutError("Service 'WSearch' did not stop within 30s")
    """
    pass


class OsConfigStateError(OsConfigError):
    """
    Snapshot / state persistence error.

    Raised when the state_manager cannot read or write the JSON snapshot
    file used for revert operations.

    Example::

        raise OsConfigStateError("Failed to write snapshot: permission denied")
    """
    pass


class OsConfigActionError(OsConfigError):
    """
    Generic action execution error.

    Raised when an action's ``apply()`` or ``revert()`` encounters an
    unexpected error that is not covered by a more specific exception type.

    Example::

        raise OsConfigActionError("SearchIndexAction.apply() failed: rc=1")
    """
    pass
