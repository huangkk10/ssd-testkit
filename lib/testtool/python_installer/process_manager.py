"""
PythonInstaller Process Manager

Handles the full install/uninstall lifecycle for a specific Python version on Windows:
  - Locate or download the official Python installer (.exe)
  - Run silent installation with configurable options
  - Verify the installation (python.exe reachable at install_path)
  - Run silent uninstallation

Download URL pattern (official python.org):
    https://www.python.org/ftp/python/<version>/python-<version>-<arch>.exe

Silent install switches:
    /quiet InstallAllUsers=0 PrependPath=1 TargetDir=<path>
"""

import os
import subprocess
import urllib.request
import shutil
import sys
from pathlib import Path
from typing import Optional

from .exceptions import (
    PythonInstallerInstallError,
    PythonInstallerVersionError,
    PythonInstallerProcessError,
    PythonInstallerTimeoutError,
)
from lib.logger import get_module_logger

logger = get_module_logger(__name__)

_DOWNLOAD_URL_TEMPLATE = (
    "https://www.python.org/ftp/python/{full_version}/python-{full_version}-{arch}.exe"
)


class PythonInstallerProcessManager:
    """
    Manages download, install, and uninstall of a Python release on Windows.

    Args:
        version:         Target version string, e.g. ``"3.11"`` or ``"3.11.8"``.
        architecture:    ``"amd64"`` or ``"win32"``. Defaults to ``"amd64"``.
        install_path:    Desired installation directory.  Empty string = Windows default.
        add_to_path:     Whether to prepend Python to PATH.
        installer_path:  Pre-existing installer path.  If empty, will be downloaded.
        download_dir:    Where to save the downloaded installer.
        timeout_seconds: Maximum seconds to wait for each subprocess.
    """

    def __init__(
        self,
        version: str,
        architecture: str = 'amd64',
        install_path: str = '',
        add_to_path: bool = True,
        installer_path: str = '',
        download_dir: str = './testlog/python_installer',
        timeout_seconds: int = 300,
    ):
        self.version = version
        self.architecture = architecture
        self.install_path = install_path
        self.add_to_path = add_to_path
        self._provided_installer_path = installer_path
        self.download_dir = Path(download_dir)
        self.timeout_seconds = timeout_seconds

        # Resolved after _resolve_full_version()
        self.full_version: str = ''
        self._resolved_installer_path: str = installer_path
        self._process: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_installed(self) -> bool:
        """
        Return True if the target Python version is reachable.

        Checks ``install_path/python.exe`` (when install_path is specified),
        or falls back to querying ``py -<major>.<minor>`` via the Python Launcher.
        """
        if self.install_path:
            exe = Path(self.install_path) / 'python.exe'
            installed = exe.is_file()
            logger.debug(f"is_installed check: {exe} -> {installed}")
            return installed

        # Fallback: query py launcher
        major_minor = '.'.join(self.version.split('.')[:2])
        try:
            result = subprocess.run(
                ['py', f'-{major_minor}', '--version'],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def install(self) -> None:
        """
        Download (if needed) and silently install Python.

        Raises:
            PythonInstallerVersionError:  Version string cannot be resolved.
            PythonInstallerInstallError:  Download or installation failed.
        """
        self._resolve_full_version()
        installer = self._ensure_installer()
        self._run_install(installer)
        self._verify_install()

    def uninstall(self) -> None:
        """
        Silently uninstall the target Python version.

        Prefers ``install_path/uninstall.exe``; falls back to re-running the
        installer with ``/uninstall``.

        Raises:
            PythonInstallerInstallError: Uninstallation process failed.
        """
        self._resolve_full_version()
        installer = self._ensure_installer()
        self._run_uninstall(installer)

    def get_executable_path(self) -> str:
        """
        Return the path to ``python.exe`` for the installed version.

        Returns an empty string if not installed.
        """
        if self.install_path:
            exe = Path(self.install_path) / 'python.exe'
            return str(exe) if exe.is_file() else ''

        major_minor = '.'.join(self.version.split('.')[:2])
        try:
            result = subprocess.run(
                ['py', f'-{major_minor}', '-c', 'import sys; print(sys.executable)'],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return ''

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_full_version(self) -> None:
        """
        Ensure ``self.full_version`` contains a 3-part version string.

        If the user provided only ``"3.11"``, this method tries to resolve it
        to the latest patch release by attempting a HEAD request to the
        download server, falling back to ``"3.11.0"`` on any failure.
        """
        parts = self.version.split('.')
        if len(parts) == 3:
            self.full_version = self.version
            return

        # Two-part version: try the .0 release first
        candidate = f"{self.version}.0"
        url = _DOWNLOAD_URL_TEMPLATE.format(
            full_version=candidate, arch=self.architecture
        )
        logger.info(f"Checking installer URL: {url}")
        try:
            req = urllib.request.Request(url, method='HEAD')
            urllib.request.urlopen(req, timeout=10)
            self.full_version = candidate
        except Exception as exc:
            logger.warning(
                f"Could not resolve full version for '{self.version}': {exc}. "
                f"Defaulting to '{candidate}'"
            )
            self.full_version = candidate

    def _ensure_installer(self) -> Path:
        """
        Return path to a valid installer .exe, downloading it if necessary.

        Raises:
            PythonInstallerInstallError: Download failed or path not found.
        """
        if self._provided_installer_path:
            p = Path(self._provided_installer_path)
            if not p.is_file():
                raise PythonInstallerInstallError(
                    f"Installer not found at provided path: {p}"
                )
            return p

        # Auto-download
        self.download_dir.mkdir(parents=True, exist_ok=True)
        filename = f"python-{self.full_version}-{self.architecture}.exe"
        dest = self.download_dir / filename

        if dest.is_file():
            logger.info(f"Using cached installer: {dest}")
            return dest

        url = _DOWNLOAD_URL_TEMPLATE.format(
            full_version=self.full_version, arch=self.architecture
        )
        logger.info(f"Downloading Python installer from {url} -> {dest}")
        try:
            urllib.request.urlretrieve(url, dest)
        except Exception as exc:
            if dest.exists():
                dest.unlink()
            raise PythonInstallerInstallError(
                f"Failed to download Python installer: {exc}"
            ) from exc

        return dest

    def _run_install(self, installer: Path) -> None:
        """Run the installer silently and raise on failure."""
        cmd = [str(installer), '/quiet', 'InstallAllUsers=0']
        if self.add_to_path:
            cmd.append('PrependPath=1')
        if self.install_path:
            cmd.append(f'TargetDir={self.install_path}')

        logger.info(f"Running installer: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            raise PythonInstallerTimeoutError(
                f"Installer timed out after {self.timeout_seconds}s"
            )
        except Exception as exc:
            raise PythonInstallerProcessError(f"Installer subprocess error: {exc}") from exc

        if result.returncode != 0:
            stderr = result.stderr.decode(errors='replace')
            raise PythonInstallerInstallError(
                f"Installer exited with code {result.returncode}: {stderr}"
            )
        logger.info("Python installation completed successfully")

    def _run_uninstall(self, installer: Path) -> None:
        """Run silent uninstallation using the downloaded/provided installer."""
        cmd = [str(installer), '/quiet', '/uninstall']
        logger.info(f"Running uninstaller: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            raise PythonInstallerTimeoutError(
                f"Uninstaller timed out after {self.timeout_seconds}s"
            )
        except Exception as exc:
            raise PythonInstallerProcessError(
                f"Uninstaller subprocess error: {exc}"
            ) from exc

        if result.returncode != 0:
            stderr = result.stderr.decode(errors='replace')
            raise PythonInstallerInstallError(
                f"Uninstaller exited with code {result.returncode}: {stderr}"
            )
        logger.info("Python uninstallation completed successfully")

    def _verify_install(self) -> None:
        """Verify the installation by running ``python --version``."""
        exe = self.get_executable_path()
        if not exe:
            raise PythonInstallerInstallError(
                f"Installation verification failed: python.exe not found "
                f"(install_path='{self.install_path}', version='{self.version}')"
            )
        try:
            result = subprocess.run(
                [exe, '--version'], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                raise PythonInstallerInstallError(
                    f"python --version returned code {result.returncode}: {result.stderr}"
                )
            installed_version = result.stdout.strip() or result.stderr.strip()
            logger.info(f"Verified install: {installed_version}")
        except subprocess.TimeoutExpired:
            raise PythonInstallerInstallError(
                "Timed out while verifying installed Python"
            )
