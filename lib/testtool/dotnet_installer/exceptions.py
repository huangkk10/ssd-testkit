"""
DotnetInstaller — Exception Hierarchy

All exceptions raised by the dotnet_installer package inherit from
``DotnetInstallerError`` so callers can catch the base class if needed.
"""


class DotnetInstallerError(Exception):
    """Base exception for all dotnet_installer errors."""


class DotnetInstallerConfigError(DotnetInstallerError):
    """Raised when configuration validation fails."""


class DotnetInstallerNotFoundError(DotnetInstallerError):
    """Raised when the installer binary cannot be located."""


class DotnetInstallerInstallError(DotnetInstallerError):
    """Raised when the silent installation process fails."""


class DotnetInstallerTimeoutError(DotnetInstallerError):
    """Raised when the installer process exceeds the configured timeout."""
