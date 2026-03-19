"""
DotnetInstaller — Process Manager

Handles detection and silent installation of the .NET Runtime on Windows.

Detection strategy
------------------
Run ``dotnet --list-runtimes`` and look for a line starting with
``Microsoft.NETCore.App <major.minor>``.  This avoids querying the registry
and works regardless of whether the SDK or the Runtime was installed.

Silent install switches
-----------------------
The bundled installer (SDK or Runtime exe) accepts the same switches as the
official offline installer::

    /install /quiet /norestart

These suppress all UI and prevent automatic reboots.
"""

from __future__ import annotations

import os
import subprocess
import winreg
from pathlib import Path
from typing import Optional

from .config import DotnetInstallerConfig
from .exceptions import (
    DotnetInstallerInstallError,
    DotnetInstallerNotFoundError,
    DotnetInstallerTimeoutError,
)
from lib.logger import get_module_logger

logger = get_module_logger(__name__)


class DotnetInstallerProcessManager:
    """
    Manages detection and silent installation of the .NET Runtime.

    Args:
        config: :class:`DotnetInstallerConfig` instance controlling paths and timeouts.
    """

    def __init__(self, config: Optional[DotnetInstallerConfig] = None) -> None:
        self._cfg = config or DotnetInstallerConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # Default install location used by the official .NET installer on Windows.
    _DOTNET_DEFAULT_PATH = Path(r"C:\Program Files\dotnet\dotnet.exe")

    def _dotnet_exe(self) -> Optional[Path]:
        """
        Resolve the ``dotnet.exe`` path.

        Tries in order:
        1. ``C:\\Program Files\\dotnet\\dotnet.exe``  (default install location on Windows)
        2. ``dotnet`` on PATH (works in CI or when PATH is already updated)

        Returns the resolved :class:`Path` when found, ``None`` otherwise.
        """
        if self._DOTNET_DEFAULT_PATH.exists():
            return self._DOTNET_DEFAULT_PATH
        # Fallback: try PATH
        import shutil as _shutil
        found = _shutil.which("dotnet")
        return Path(found) if found else None

    def is_installed(self) -> bool:
        """
        Return ``True`` if the required .NET Runtime is already present.

        Uses the fixed install path ``C:\\Program Files\\dotnet\\dotnet.exe``
        first (so detection works immediately after installation without
        waiting for PATH to refresh), then falls back to ``dotnet`` on PATH.
        """
        target = self._cfg.target_version
        exe = self._dotnet_exe()
        if exe is None:
            logger.info("[DotnetInstaller] dotnet.exe not found — runtime absent")
            return False
        try:
            result = subprocess.run(
                [str(exe), "--list-runtimes"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            for line in result.stdout.splitlines():
                # e.g. "Microsoft.NETCore.App 7.0.20 [C:\Program Files\dotnet\...]"
                if line.startswith(f"Microsoft.NETCore.App {target}"):
                    logger.info(
                        f"[DotnetInstaller] .NET {target} runtime found: {line.strip()}"
                    )
                    return True
            logger.info(
                f"[DotnetInstaller] .NET {target} runtime not found in: "
                f"{result.stdout.strip()!r}"
            )
            return False
        except subprocess.TimeoutExpired:
            logger.warning("[DotnetInstaller] 'dotnet --list-runtimes' timed out")
            return False

    def install(self) -> None:
        """
        Run the bundled installer silently.

        Raises:
            DotnetInstallerNotFoundError: The installer ``.exe`` does not exist.
            DotnetInstallerInstallError:  The installer process returned non-zero.
            DotnetInstallerTimeoutError:  Installation exceeded the configured timeout.
        """
        installer = self._cfg.resolved_installer()
        if not installer.exists():
            raise DotnetInstallerNotFoundError(
                f"[DotnetInstaller] Installer not found: {installer}\n"
                f"Place the installer at: {self._cfg.installer_path}"
            )

        logger.info(f"[DotnetInstaller] Running installer: {installer}")
        try:
            result = subprocess.run(
                [str(installer), "/install", "/quiet", "/norestart"],
                capture_output=True,
                text=True,
                timeout=self._cfg.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise DotnetInstallerTimeoutError(
                f"[DotnetInstaller] Installer timed out after "
                f"{self._cfg.timeout_seconds}s: {installer}"
            ) from exc

        if result.returncode != 0:
            raise DotnetInstallerInstallError(
                f"[DotnetInstaller] Installer failed (rc={result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

        logger.info(
            f"[DotnetInstaller] .NET {self._cfg.target_version} installed successfully"
        )

        # Set DOTNET_ROOT as a persistent system environment variable so that
        # child processes spawned by Node.js (e.g. GlitterMountain.exe inside PHM)
        # can locate the runtime even when PATH is not updated in the current session.
        dotnet_root = str(self._DOTNET_DEFAULT_PATH.parent)
        self._set_system_env("DOTNET_ROOT", dotnet_root)
        # Also update the current process environment immediately so post-install
        # detection by _dotnet_exe() works without a reboot.
        os.environ.setdefault("DOTNET_ROOT", dotnet_root)
        logger.info(f"[DotnetInstaller] DOTNET_ROOT set to: {dotnet_root}")

    def ensure(self) -> bool:
        """
        Ensure the runtime is present, installing from the bundled exe if needed.

        Returns:
            ``True``  if the runtime is ready (already present or just installed).
            ``False`` if installation failed (exception is caught and logged).
        """
        if self.is_installed():
            logger.info(
                f"[DotnetInstaller] .NET {self._cfg.target_version} already installed — skipping"
            )
            # Ensure DOTNET_ROOT is set even when skipping installation,
            # so PHM's Node.js child processes (GlitterMountain.exe) can
            # locate the runtime regardless of PATH inheritance.
            dotnet_root = str(self._DOTNET_DEFAULT_PATH.parent)
            if not os.environ.get("DOTNET_ROOT"):
                self._set_system_env("DOTNET_ROOT", dotnet_root)
                os.environ["DOTNET_ROOT"] = dotnet_root
                logger.info(f"[DotnetInstaller] DOTNET_ROOT set to: {dotnet_root}")
            return True

        logger.info(
            f"[DotnetInstaller] .NET {self._cfg.target_version} not found — installing..."
        )
        try:
            self.install()
            return self.is_installed()
        except (
            DotnetInstallerNotFoundError,
            DotnetInstallerInstallError,
            DotnetInstallerTimeoutError,
        ) as exc:
            logger.error(f"[DotnetInstaller] Installation failed: {exc}")
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_system_env(name: str, value: str) -> None:
        """
        Persist *name=value* as a Windows **machine-level** environment variable.

        Uses the registry key
        ``HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment``
        so the variable is inherited by all new processes after the next
        environment-block refresh (no reboot required for new processes;
        existing Node.js processes will see it after they restart).

        Falls back to a ``setx /M`` subprocess if registry access fails.
        """
        reg_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                reg_path,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
            logger.info(
                f"[DotnetInstaller] System env set via registry: {name}={value}"
            )
        except OSError as exc:
            logger.warning(
                f"[DotnetInstaller] Registry set failed ({exc}); "
                f"falling back to setx /M"
            )
            try:
                subprocess.run(
                    ["setx", "/M", name, value],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                logger.info(
                    f"[DotnetInstaller] System env set via setx: {name}={value}"
                )
            except Exception as exc2:
                logger.warning(
                    f"[DotnetInstaller] setx also failed: {exc2} — "
                    f"DOTNET_ROOT may not persist across processes"
                )
