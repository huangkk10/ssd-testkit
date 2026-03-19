"""
DotnetInstaller — Configuration

Centralises installer path, target runtime version, and timeout settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# Default relative path to the bundled installer (relative to cwd / test-case dir).
DEFAULT_INSTALLER_RELPATH = "bin/net_7_sdk/dotnet-sdk-7.0.410-win-x64.exe"

# The minimum .NET major.minor we require (7.0).
DEFAULT_TARGET_VERSION = "7.0"

# Seconds to wait for the silent installer to finish.
DEFAULT_TIMEOUT = 300


@dataclass
class DotnetInstallerConfig:
    """
    Configuration for the .NET installer.

    Args:
        installer_path:   Absolute or cwd-relative path to the ``.exe`` installer.
                          Defaults to ``bin/net_7_sdk/dotnet-sdk-7.0.410-win-x64.exe``.
        target_version:   Minimum ``"major.minor"`` string to look for when checking
                          existing runtimes.  Default: ``"7.0"``.
        timeout_seconds:  Maximum seconds to wait for the installer subprocess.
    """

    installer_path: str = DEFAULT_INSTALLER_RELPATH
    target_version: str = DEFAULT_TARGET_VERSION
    timeout_seconds: int = DEFAULT_TIMEOUT

    def resolved_installer(self) -> Path:
        """Return the installer path as an absolute ``Path``."""
        p = Path(self.installer_path)
        return p if p.is_absolute() else (Path.cwd() / p)
