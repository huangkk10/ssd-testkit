"""
DotnetInstaller Package

Ensures that the required .NET Runtime is present on the current machine.
Designed for use in test precondition steps where ``GlitterMountain.exe``
(PHM's Modern Standby worker) requires .NET 7.0 x64 to be installed.

The bundled installer is resolved relative to the **current working directory**
at call time, so tests should call :func:`ensure_dotnet_runtime` *after*
``os.chdir()`` into their test-case directory (where ``bin/net_7_sdk/`` lives).

Installer path convention::

    <test_case_dir>/
    └── bin/
        └── net_7_sdk/
            └── dotnet-sdk-7.0.410-win-x64.exe

Main Components
---------------
- :class:`DotnetInstallerController`    Threading wrapper (non-blocking)
- :class:`DotnetInstallerConfig`        Configuration (installer path, version, timeout)
- :class:`DotnetInstallerProcessManager` Install / detection logic
- :func:`ensure_dotnet_runtime`         Convenience one-liner for precondition steps

Usage — simple blocking call::

    from lib.testtool.dotnet_installer import ensure_dotnet_runtime

    ok = ensure_dotnet_runtime(logger)
    if not ok:
        pytest.fail(".NET 7.0 runtime could not be installed")

Usage — custom installer path::

    from lib.testtool.dotnet_installer import ensure_dotnet_runtime, DotnetInstallerConfig

    ok = ensure_dotnet_runtime(
        logger,
        config=DotnetInstallerConfig(installer_path="bin/net_7_sdk/dotnet-sdk-7.0.410-win-x64.exe"),
    )

Usage — threading controller::

    from lib.testtool.dotnet_installer import DotnetInstallerController

    ctrl = DotnetInstallerController()
    ctrl.start()
    ctrl.join(timeout=300)
    assert ctrl.status is True
"""

from __future__ import annotations

import logging
from typing import Optional

from .config import DotnetInstallerConfig
from .controller import DotnetInstallerController
from .process_manager import DotnetInstallerProcessManager
from .exceptions import (
    DotnetInstallerError,
    DotnetInstallerConfigError,
    DotnetInstallerNotFoundError,
    DotnetInstallerInstallError,
    DotnetInstallerTimeoutError,
)

__version__ = "1.0.0"

__all__ = [
    "ensure_dotnet_runtime",
    "DotnetInstallerController",
    "DotnetInstallerConfig",
    "DotnetInstallerProcessManager",
    "DotnetInstallerError",
    "DotnetInstallerConfigError",
    "DotnetInstallerNotFoundError",
    "DotnetInstallerInstallError",
    "DotnetInstallerTimeoutError",
]


def ensure_dotnet_runtime(
    logger: Optional[logging.Logger] = None,
    config: Optional[DotnetInstallerConfig] = None,
) -> bool:
    """
    Ensure the .NET Runtime required by PHM is installed on this machine.

    Checks for an existing installation first; installs from the bundled
    ``bin/net_7_sdk/*.exe`` if missing.  All messages are sent to *logger*
    (silently discarded if ``None``).

    Args:
        logger: Optional Python logger for progress messages.
        config: Optional :class:`DotnetInstallerConfig`.  Defaults are used if omitted.

    Returns:
        ``True`` if the runtime is ready, ``False`` if installation failed.
    """
    mgr = DotnetInstallerProcessManager(config or DotnetInstallerConfig())
    return mgr.ensure()
