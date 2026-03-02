"""
PHM (Powerhouse Mountain) Process Manager

Process lifecycle management for PHM: install, uninstall, launch, terminate.
"""

import os
import subprocess
import time
import winreg
from typing import Optional
from pathlib import Path

from .exceptions import PHMInstallError, PHMProcessError, PHMTimeoutError
from lib.logger import get_module_logger

logger = get_module_logger(__name__)

# Registry key where PHM registers its uninstaller
# Confirmed from real installation: DisplayName == "Powerhouse Mountain"
_PHM_REGISTRY_KEYS = [
    r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Powerhouse Mountain',
    r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Powerhouse Mountain',
]


class PHMProcessManager:
    """
    Process manager for PHM (Powerhouse Mountain) tool.

    Handles:
    - Installation and uninstallation of PHM
    - Launching the PHM GUI
    - Terminating the PHM process
    - Installation status detection via filesystem and registry

    Example:
        >>> manager = PHMProcessManager(
        ...     install_path='C:\\\\Program Files\\\\PowerhouseMountain',
        ...     executable_name='PowerhouseMountain.exe',
        ... )
        >>> if not manager.is_installed():
        ...     manager.install(
        ...         installer_path='./bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe',
        ...         timeout=600,
        ...     )
        >>> manager.launch()
    """

    def __init__(
        self,
        install_path: str,
        executable_name: str = 'PHM.exe',
    ):
        """
        Initialize PHM process manager.

        Args:
            install_path: Target installation directory.
            executable_name: Main PHM executable filename.
        """
        self.install_path = Path(install_path)
        self.executable_name = executable_name
        self.executable_path = self.install_path / executable_name

        # Process tracking
        self._process: Optional[subprocess.Popen] = None
        self._pid: Optional[int] = None

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    def is_installed(self) -> bool:
        """
        Check if PHM is installed.

        Checks both the filesystem (executable presence) and the Windows
        registry for an uninstall entry.

        Returns:
            True if PHM appears to be installed.

        Example:
            >>> manager = PHMProcessManager('C:\\\\Program Files\\\\Intel\\\\Powerhouse Mountain')
            >>> print(manager.is_installed())
        """
        # Filesystem check (fastest)
        if self.executable_path.exists() and self.executable_path.is_file():
            return True

        # Fallback: scan registry uninstall keys
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for subkey in _PHM_REGISTRY_KEYS:
                try:
                    with winreg.OpenKey(hive, subkey):
                        return True
                except OSError:
                    continue

        return False

    def install(
        self,
        installer_path: str,
        silent_switch: str = '/S',
        timeout: int = 600,
    ) -> bool:
        """
        Run PHM installer silently.

        Args:
            installer_path: Full path to the PHM installer .exe.
            silent_switch: Silent install switch (default ``/S`` for NSIS).
                           Use ``/s /v"/qn"`` for InstallShield.
            timeout: Maximum seconds to wait for installation to complete.

        Returns:
            True if installation succeeded.

        Raises:
            PHMInstallError: If installer not found or exits with non-zero code.
            PHMTimeoutError: If installation exceeds *timeout* seconds.

        Example:
            >>> manager.install(
            ...     installer_path='./bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe',
            ...     timeout=600,
            ... )
        """
        installer = Path(installer_path)
        if not installer.exists():
            raise PHMInstallError(f"Installer not found: {installer_path}")

        logger.info(f"Installing PHM from: {installer_path}")
        try:
            result = subprocess.run(
                [str(installer), silent_switch],
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise PHMTimeoutError(
                f"PHM installation timed out after {timeout} seconds"
            )

        if result.returncode not in (0, 3010):  # 3010 = reboot required
            stderr = result.stderr.decode(errors='replace')
            raise PHMInstallError(
                f"PHM installation failed (exit code {result.returncode}): {stderr}"
            )

        # Give installer a moment to finalize registry writes
        time.sleep(2)

        if not self.is_installed():
            raise PHMInstallError(
                "Installer completed but PHM executable was not found. "
                "The silent switch may be incorrect — check PHM installer flags."
            )

        logger.info("PHM installed successfully")
        return True

    def uninstall(self, timeout: int = 120) -> bool:
        """
        Uninstall PHM silently.

        Searches for an ``uninstall.exe`` or ``uninst.exe`` in the install
        directory; falls back to the registry ``UninstallString``.

        Args:
            timeout: Maximum seconds to wait for uninstallation.

        Returns:
            True if uninstallation completed without error.

        Raises:
            PHMInstallError: If no uninstaller is found.
            PHMTimeoutError: If uninstallation exceeds *timeout* seconds.
        """
        # Strategy 1: look for uninstaller inside install dir
        for name in ('uninstall.exe', 'uninst.exe', 'Uninstall.exe'):
            uninstaller = self.install_path / name
            if uninstaller.exists():
                logger.info(f"Uninstalling PHM via: {uninstaller}")
                try:
                    subprocess.run(
                        [str(uninstaller), '/S'],
                        capture_output=True,
                        timeout=timeout,
                    )
                except subprocess.TimeoutExpired:
                    raise PHMTimeoutError(
                        f"PHM uninstall timed out after {timeout} seconds"
                    )
                logger.info("PHM uninstalled successfully")
                return True

        # Strategy 2: registry QuietUninstallString / UninstallString
        # PHM uses WiX bundler; QuietUninstallString = "phm_setup_nda.exe" /uninstall /quiet
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for subkey in _PHM_REGISTRY_KEYS:
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        # Prefer QuietUninstallString (has /quiet flag already)
                        try:
                            uninstall_cmd, _ = winreg.QueryValueEx(key, 'QuietUninstallString')
                        except OSError:
                            uninstall_cmd, _ = winreg.QueryValueEx(key, 'UninstallString')
                            uninstall_cmd = uninstall_cmd + ' /quiet'
                    logger.info(f"Uninstalling PHM via registry: {uninstall_cmd}")
                    subprocess.run(
                        uninstall_cmd,
                        shell=True,
                        capture_output=True,
                        timeout=timeout,
                    )
                    logger.info("PHM uninstalled successfully")
                    return True
                except OSError:
                    continue

        raise PHMInstallError(
            "No PHM uninstaller found. "
            "Checked install directory and Windows registry."
        )

    # ------------------------------------------------------------------
    # Process lifecycle
    # ------------------------------------------------------------------

    def launch(self, extra_args: Optional[list] = None) -> subprocess.Popen:
        """
        Launch the PHM GUI application.

        Args:
            extra_args: Additional command-line arguments for PHM.

        Returns:
            The spawned :class:`subprocess.Popen` handle.

        Raises:
            PHMProcessError: If the executable does not exist.

        Example:
            >>> proc = manager.launch()
        """
        if not self.executable_path.exists():
            raise PHMProcessError(
                f"PHM executable not found: {self.executable_path}. "
                "Please install PHM first."
            )

        cmd = [str(self.executable_path)] + (extra_args or [])
        logger.info(f"Launching PHM: {' '.join(cmd)}")
        # PHM is a Node.js app — cwd MUST be the install directory
        # so that app.js is found on the current working directory
        self._process = subprocess.Popen(cmd, cwd=str(self.install_path))
        self._pid = self._process.pid
        logger.info(f"PHM started with PID {self._pid}")
        return self._process

    def terminate(self, timeout: int = 30) -> None:
        """
        Gracefully terminate the PHM process.

        Sends SIGTERM and waits up to *timeout* seconds; kills if necessary.

        Args:
            timeout: Seconds to wait before escalating to kill.
        """
        if self._process is None:
            logger.debug("terminate() called but no tracked process")
            return

        logger.info(f"Terminating PHM process (PID {self._pid})")
        self._process.terminate()
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("PHM did not terminate gracefully — killing")
            self._process.kill()
            self._process.wait()

        self._process = None
        self._pid = None
        logger.info("PHM process terminated")

    def kill_by_name(self, process_name: str = 'PHM.exe') -> None:
        """
        Force-kill any running PHM.exe processes by name (taskkill).

        Useful as a global cleanup when PID is unknown.

        Args:
            process_name: Name of the process to kill (default ``PHM.exe``).
        """
        logger.info(f"Force-killing all '{process_name}' processes")
        subprocess.run(
            ['taskkill', '/F', '/IM', process_name],
            capture_output=True,
        )

    def is_running(self) -> bool:
        """
        Check if the tracked PHM process is still alive.

        Returns:
            True if the process is running, False otherwise.
        """
        if self._process is None or self._pid is None:
            return False
        return self._process.poll() is None

    @property
    def pid(self) -> Optional[int]:
        """PID of the currently tracked PHM process, or None."""
        return self._pid
