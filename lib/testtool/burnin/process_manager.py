"""
BurnIN Process Manager

This module provides process lifecycle management for BurnIN test tool.
"""

import os
import subprocess
import time
import psutil
from typing import Optional, List
from pathlib import Path

from .exceptions import (
    BurnInProcessError,
    BurnInInstallError,
    BurnInTimeoutError,
)
from lib.logger import get_module_logger

# Initialize module-level logger
logger = get_module_logger(__name__)


class BurnInProcessManager:
    """
    Process manager for BurnIN test tool.
    
    This class handles:
    - Installation and uninstallation
    - Process startup and termination
    - PID tracking and process monitoring
    - Process status checks
    
    Example:
        >>> manager = BurnInProcessManager(
        ...     install_path="C:\\Program Files\\BurnInTest",
        ...     executable_name="bit.exe"
        ... )
        >>> 
        >>> # Check if installed
        >>> if not manager.is_installed():
        ...     manager.install(installer_path="./installer.exe")
        >>> 
        >>> # Start process
        >>> manager.start_process(script_path="./test.bits")
        >>> 
        >>> # Monitor process
        >>> while manager.is_running():
        ...     time.sleep(1)
        >>> 
        >>> # Cleanup
        >>> manager.stop_process()
    """
    
    def __init__(
        self,
        install_path: str,
        executable_name: str = "bit.exe"
    ):
        """
        Initialize process manager.
        
        Args:
            install_path: Installation directory path
            executable_name: Name of BurnIN executable (bit.exe or bit64.exe)
        
        Example:
            >>> manager = BurnInProcessManager(
            ...     install_path="C:\\Program Files\\BurnInTest",
            ...     executable_name="bit.exe"
            ... )
        """
        self.install_path = Path(install_path)
        self.executable_name = executable_name
        self.executable_path = self.install_path / executable_name
        
        # Fallback executable (bit.exe if bit64.exe not found)
        self.fallback_executable = self.install_path / 'bit.exe' if executable_name == 'bit64.exe' else None
        
        # Process tracking
        self._process: Optional[subprocess.Popen] = None
        self._pid: Optional[int] = None
    
    def is_installed(self) -> bool:
        """
        Check if BurnIN is installed.
        
        Returns:
            bool: True if executable exists (checks both primary and fallback)
        
        Example:
            >>> manager = BurnInProcessManager("C:\\Program Files\\BurnInTest")
            >>> if manager.is_installed():
            ...     print("BurnIN is installed")
        """
        # Check primary executable
        if self.executable_path.exists() and self.executable_path.is_file():
            return True
        
        # Check fallback executable
        if self.fallback_executable and self.fallback_executable.exists() and self.fallback_executable.is_file():
            return True
        
        return False
    
    def _get_executable(self) -> Path:
        """
        Get the actual executable path (with fallback support).
        
        Returns:
            Path: Primary executable if exists, otherwise fallback
        """
        if self.executable_path.exists():
            return self.executable_path
        elif self.fallback_executable and self.fallback_executable.exists():
            return self.fallback_executable
        else:
            raise BurnInProcessError(f"BurnIN executable not found: {self.executable_path}")
    
    def install(
        self,
        installer_path: str,
        license_path: Optional[str] = None,
        silent: bool = True,
        timeout: int = 300
    ) -> bool:
        """
        Install BurnIN test tool.
        
        Args:
            installer_path: Path to installer executable
            license_path: Path to license key file (optional)
            silent: Run installer in silent mode
            timeout: Installation timeout in seconds
        
        Returns:
            bool: True if installation succeeded
        
        Raises:
            BurnInInstallError: If installation fails
            FileNotFoundError: If installer not found
            BurnInTimeoutError: If installation times out
        
        Example:
            >>> manager.install(
            ...     installer_path="./installer.exe",
            ...     license_path="./key.dat",
            ...     silent=True
            ... )
            True
        """
        installer = Path(installer_path).resolve()

        if not installer.exists():
            raise FileNotFoundError(f"Installer not found: {installer_path}")

        # Build command string (no shell=True).
        # Pass as a string directly to CreateProcess (Windows behaviour) so that
        # the installer's UAC elevation manifest is honoured correctly.
        # Using shell=True routes through cmd.exe which can break the elevated
        # child's stdin handle and cause Inno Setup to cancel (exit code 5).
        # This matches the original BurnIN.py: subprocess.run(cmd_string).
        if silent:
            flags = '/SILENT /SUPPRESSMSGBOXES /NORESTART'
        else:
            flags = ''
        cmd = f'"{installer}" {flags} /DIR="{self.install_path}"'.strip()

        logger.info(f"Installer command: {cmd}")

        try:
            # Run installer: string + no shell=True → direct CreateProcess call.
            # No capture_output so that stdout/stderr handles are inherited,
            # allowing UAC elevation to proceed without pipe errors.
            result = subprocess.run(
                cmd,
                timeout=timeout
            )

            logger.info(f"Installer returncode: {result.returncode}")

            if result.returncode != 0:
                error_msg = f"Installation failed with code {result.returncode}"
                raise BurnInInstallError(error_msg)
            
            # Copy license file if provided
            if license_path:
                self._install_license(license_path)
            
            # Verify installation
            if not self.is_installed():
                raise BurnInInstallError(
                    f"Installation completed but executable not found: {self.executable_path}"
                )
            
            return True
            
        except subprocess.TimeoutExpired:
            raise BurnInTimeoutError(f"Installation timeout after {timeout} seconds")
        except subprocess.SubprocessError as e:
            raise BurnInInstallError(f"Installation error: {e}")
    
    def _install_license(self, license_path: str) -> None:
        """
        Install license key file.
        
        Args:
            license_path: Path to license key file
        
        Raises:
            FileNotFoundError: If license file not found
            BurnInInstallError: If license copy fails
        """
        import shutil
        
        license_file = Path(license_path)
        if not license_file.exists():
            raise FileNotFoundError(f"License file not found: {license_path}")
        
        # Copy license to installation directory
        target = self.install_path / license_file.name
        
        try:
            shutil.copy2(license_file, target)
        except Exception as e:
            raise BurnInInstallError(f"Failed to install license: {e}")
    
    def uninstall(self, timeout: int = 300) -> bool:
        """
        Uninstall BurnIN test tool.
        
        Args:
            timeout: Uninstallation timeout in seconds
        
        Returns:
            bool: True if uninstallation succeeded
        
        Raises:
            BurnInInstallError: If uninstallation fails
        
        Example:
            >>> manager.uninstall()
            True
        """
        if not self.is_installed():
            return True  # Already uninstalled
        
        # Look for uninstaller
        uninstaller = self.install_path / "unins000.exe"
        
        if not uninstaller.exists():
            # Fallback: no uninstaller (manually copied), kill process then force remove directory
            import shutil
            import psutil
            logger.warning(
                f"Uninstaller not found: {uninstaller}. "
                f"Falling back to force-removing install directory."
            )
            # Kill any running bit.exe / bit64.exe before removing
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() in ('bit.exe', 'bit64.exe'):
                        logger.warning(f"Killing running BurnIN process: PID {proc.pid}")
                        proc.kill()
                        proc.wait(timeout=10)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            try:
                shutil.rmtree(self.install_path)
                logger.info(f"Forcefully removed install directory: {self.install_path}")
                return True
            except Exception as e:
                raise BurnInInstallError(
                    f"Uninstaller not found and force removal failed: {e}"
                )
        
        try:
            # Run uninstaller silently
            result = subprocess.run(
                [str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES'],
                timeout=timeout,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                error_msg = f"Uninstallation failed with code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                raise BurnInInstallError(error_msg)
            
            return True
            
        except subprocess.TimeoutExpired:
            raise BurnInTimeoutError(f"Uninstallation timeout after {timeout} seconds")
        except subprocess.SubprocessError as e:
            raise BurnInInstallError(f"Uninstallation error: {e}")
    
    def start_process(
        self,
        script_path: str,
        timeout: int = 30
    ) -> int:
        """
        Start BurnIN process with script.
        
        Args:
            script_path: Path to .bits script file
            timeout: Process startup timeout in seconds
        
        Returns:
            int: Process ID (PID)
        
        Raises:
            BurnInProcessError: If process fails to start
            FileNotFoundError: If executable or script not found
            BurnInTimeoutError: If process startup times out
        
        Example:
            >>> pid = manager.start_process("./test.bits")
            >>> print(f"BurnIN started with PID {pid}")
        """
        if not self.is_installed():
            raise BurnInProcessError("BurnIN not installed")
        
        # Get actual executable (with fallback support)
        executable = self._get_executable()
        logger.info(f"Using BurnIN executable: {executable}")
        
        script = Path(script_path)
        if not script.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")
        
        # Stop any existing process
        if self.is_running():
            self.stop_process()
        
        # Build command with BurnIN flags
        # -S: Run script file
        # -K: Close on completion
        # -R: Run tests immediately
        # -W: Windowed mode (not minimized)
        cmd = [
            str(executable),
            "-S", str(script.absolute()),
            "-K", "-R", "-W"
        ]
        
        try:
            # Start process
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            self._pid = self._process.pid
            
            # Wait for process to stabilize
            time.sleep(2)
            
            # Check if process is still running
            if not self.is_running():
                stdout, stderr = self._process.communicate(timeout=5)
                error_msg = f"Process terminated immediately after start"
                if stderr:
                    error_msg += f": {stderr.decode()}"
                raise BurnInProcessError(error_msg)
            
            return self._pid
            
        except subprocess.SubprocessError as e:
            raise BurnInProcessError(f"Failed to start process: {e}")
    
    def stop_process(self, timeout: int = 10) -> bool:
        """
        Stop BurnIN process gracefully.
        
        Args:
            timeout: Timeout for graceful shutdown in seconds
        
        Returns:
            bool: True if process stopped successfully
        
        Raises:
            BurnInProcessError: If process cannot be stopped
        
        Example:
            >>> manager.stop_process(timeout=10)
            True
        """
        if not self.is_running():
            return True
        
        try:
            # Try graceful termination first
            if self._process:
                self._process.terminate()
                
                # Wait for process to exit
                try:
                    self._process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Force kill if timeout
                    self._process.kill()
                    self._process.wait(timeout=5)
            
            # Also kill by PID if psutil available
            elif self._pid:
                process = psutil.Process(self._pid)
                process.terminate()
                process.wait(timeout=timeout)
            
            self._process = None
            self._pid = None
            
            return True
            
        except psutil.NoSuchProcess:
            # Process already gone
            self._process = None
            self._pid = None
            return True
        except Exception as e:
            raise BurnInProcessError(f"Failed to stop process: {e}")
    
    def kill_process(self) -> bool:
        """
        Force kill BurnIN process immediately.
        
        Returns:
            bool: True if process killed successfully
        
        Raises:
            BurnInProcessError: If process cannot be killed
        
        Example:
            >>> manager.kill_process()
            True
        """
        if not self.is_running():
            return True
        
        try:
            if self._process:
                self._process.kill()
                self._process.wait(timeout=5)
            elif self._pid:
                process = psutil.Process(self._pid)
                process.kill()
                process.wait(timeout=5)
            
            self._process = None
            self._pid = None
            
            return True
            
        except psutil.NoSuchProcess:
            self._process = None
            self._pid = None
            return True
        except Exception as e:
            raise BurnInProcessError(f"Failed to kill process: {e}")
    
    def is_running(self) -> bool:
        """
        Check if BurnIN process is running.
        
        Returns:
            bool: True if process is running
        
        Example:
            >>> if manager.is_running():
            ...     print("BurnIN is running")
        """
        # Check subprocess object first
        if self._process:
            return self._process.poll() is None
        
        # Check by PID if available
        if self._pid:
            try:
                process = psutil.Process(self._pid)
                return process.is_running()
            except psutil.NoSuchProcess:
                return False
        
        return False
    
    def get_pid(self) -> Optional[int]:
        """
        Get process ID of running BurnIN process.
        
        Returns:
            Optional[int]: PID if process is running, None otherwise
        
        Example:
            >>> pid = manager.get_pid()
            >>> if pid:
            ...     print(f"BurnIN PID: {pid}")
        """
        if self.is_running():
            return self._pid
        return None
    
    def get_process_info(self) -> Optional[dict]:
        """
        Get detailed process information.
        
        Returns:
            Optional[dict]: Process info dict or None if not running
        
        Example:
            >>> info = manager.get_process_info()
            >>> if info:
            ...     print(f"CPU: {info['cpu_percent']}%")
            ...     print(f"Memory: {info['memory_mb']} MB")
        """
        if not self.is_running() or not self._pid:
            return None
        
        try:
            process = psutil.Process(self._pid)
            
            # Get process info
            with process.oneshot():
                return {
                    'pid': process.pid,
                    'name': process.name(),
                    'status': process.status(),
                    'cpu_percent': process.cpu_percent(interval=0.1),
                    'memory_mb': process.memory_info().rss / 1024 / 1024,
                    'num_threads': process.num_threads(),
                    'create_time': process.create_time(),
                }
        except psutil.NoSuchProcess:
            return None
        except Exception:
            return None
    
    def find_existing_process(self) -> Optional[int]:
        """
        Find existing BurnIN process by executable name.
        
        Returns:
            Optional[int]: PID of found process, None if not found
        
        Example:
            >>> pid = manager.find_existing_process()
            >>> if pid:
            ...     print(f"Found existing BurnIN process: {pid}")
        """
        try:
            for process in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    # Check if process name matches
                    if process.info['name'].lower() == self.executable_name.lower():
                        # Verify executable path if available
                        if process.info.get('exe'):
                            exe_path = Path(process.info['exe'])
                            if exe_path.parent == self.install_path:
                                return process.info['pid']
                        else:
                            # If exe path not available, just match by name
                            return process.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        return None
    
    def attach_to_process(self, pid: int) -> bool:
        """
        Attach to existing BurnIN process.
        
        Args:
            pid: Process ID to attach to
        
        Returns:
            bool: True if successfully attached
        
        Raises:
            BurnInProcessError: If process not found or cannot attach
        
        Example:
            >>> existing_pid = manager.find_existing_process()
            >>> if existing_pid:
            ...     manager.attach_to_process(existing_pid)
        """
        try:
            process = psutil.Process(pid)
            
            # Verify it's the correct executable
            if not process.name().lower() == self.executable_name.lower():
                raise BurnInProcessError(
                    f"Process {pid} is not {self.executable_name}"
                )
            
            self._pid = pid
            self._process = None  # Can't get subprocess.Popen for existing process
            
            return True
            
        except psutil.NoSuchProcess:
            raise BurnInProcessError(f"Process {pid} not found")
        except Exception as e:
            raise BurnInProcessError(f"Failed to attach to process {pid}: {e}")
