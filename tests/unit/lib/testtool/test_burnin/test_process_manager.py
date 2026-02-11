"""
Unit tests for BurnIN process manager module.
"""

import pytest
import subprocess
import psutil
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from pathlib import Path

from lib.testtool.burnin.process_manager import BurnInProcessManager
from lib.testtool.burnin.exceptions import (
    BurnInProcessError,
    BurnInInstallError,
    BurnInTimeoutError,
)


class TestBurnInProcessManager:
    """Test suite for BurnInProcessManager class."""
    
    def test_init(self):
        """Test process manager initialization."""
        manager = BurnInProcessManager(
            install_path="C:\\Program Files\\BurnInTest",
            executable_name="bit.exe"
        )
        
        assert manager.install_path == Path("C:\\Program Files\\BurnInTest")
        assert manager.executable_name == "bit.exe"
        assert manager.executable_path == Path("C:\\Program Files\\BurnInTest\\bit.exe")
        assert manager._process is None
        assert manager._pid is None
    
    def test_init_default_executable(self):
        """Test initialization with default executable name."""
        manager = BurnInProcessManager("C:\\test")
        
        assert manager.executable_name == "bit.exe"
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_file')
    def test_is_installed_true(self, mock_is_file, mock_exists):
        """Test is_installed returns True when executable exists."""
        mock_exists.return_value = True
        mock_is_file.return_value = True
        
        manager = BurnInProcessManager("C:\\test")
        
        assert manager.is_installed() is True
    
    @patch('pathlib.Path.exists')
    def test_is_installed_false(self, mock_exists):
        """Test is_installed returns False when executable doesn't exist."""
        mock_exists.return_value = False
        
        manager = BurnInProcessManager("C:\\test")
        
        assert manager.is_installed() is False
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    @patch.object(BurnInProcessManager, 'is_installed')
    def test_install_success(self, mock_is_installed, mock_exists, mock_run):
        """Test successful installation."""
        # Setup
        mock_exists.return_value = True
        mock_is_installed.return_value = True
        mock_run.return_value = Mock(returncode=0, stderr='')
        
        manager = BurnInProcessManager("C:\\test")
        
        # Execute
        result = manager.install(installer_path="./installer.exe")
        
        # Verify
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'installer.exe' in args[0]
        assert '/VERYSILENT' in args
        assert any('/DIR=' in arg for arg in args)
    
    @patch('pathlib.Path.exists')
    def test_install_installer_not_found(self, mock_exists):
        """Test installation fails when installer not found."""
        mock_exists.return_value = False
        
        manager = BurnInProcessManager("C:\\test")
        
        with pytest.raises(FileNotFoundError) as exc_info:
            manager.install(installer_path="./missing.exe")
        
        assert 'Installer not found' in str(exc_info.value)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_install_failure(self, mock_exists, mock_run):
        """Test installation failure."""
        mock_exists.return_value = True
        mock_run.return_value = Mock(returncode=1, stderr='Error')
        
        manager = BurnInProcessManager("C:\\test")
        
        with pytest.raises(BurnInInstallError) as exc_info:
            manager.install(installer_path="./installer.exe")
        
        assert 'Installation failed' in str(exc_info.value)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_install_timeout(self, mock_exists, mock_run):
        """Test installation timeout."""
        mock_exists.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='test', timeout=300)
        
        manager = BurnInProcessManager("C:\\test")
        
        with pytest.raises(BurnInTimeoutError) as exc_info:
            manager.install(installer_path="./installer.exe")
        
        assert 'Installation timeout' in str(exc_info.value)
    
    @patch('shutil.copy2')
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    @patch.object(BurnInProcessManager, 'is_installed')
    def test_install_with_license(self, mock_is_installed, mock_exists, mock_run, mock_copy):
        """Test installation with license file."""
        mock_exists.return_value = True
        mock_is_installed.return_value = True
        mock_run.return_value = Mock(returncode=0, stderr='')
        
        manager = BurnInProcessManager("C:\\test")
        
        result = manager.install(
            installer_path="./installer.exe",
            license_path="./key.dat"
        )
        
        assert result is True
        mock_copy.assert_called_once()
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    @patch.object(BurnInProcessManager, 'is_installed')
    def test_uninstall_success(self, mock_is_installed, mock_exists, mock_run):
        """Test successful uninstallation."""
        # First call: is_installed() check (True)
        # Second call: uninstaller exists check (True)
        mock_is_installed.return_value = True
        mock_exists.return_value = True
        mock_run.return_value = Mock(returncode=0, stderr='')
        
        manager = BurnInProcessManager("C:\\test")
        
        result = manager.uninstall()
        
        assert result is True
        mock_run.assert_called_once()
    
    @patch.object(BurnInProcessManager, 'is_installed')
    def test_uninstall_not_installed(self, mock_is_installed):
        """Test uninstall when not installed."""
        mock_is_installed.return_value = False
        
        manager = BurnInProcessManager("C:\\test")
        
        result = manager.uninstall()
        
        assert result is True  # Already uninstalled
    
    @patch('pathlib.Path.exists')
    @patch.object(BurnInProcessManager, 'is_installed')
    def test_uninstall_uninstaller_not_found(self, mock_is_installed, mock_exists):
        """Test uninstall fails when uninstaller not found."""
        mock_is_installed.return_value = True
        mock_exists.return_value = False
        
        manager = BurnInProcessManager("C:\\test")
        
        with pytest.raises(BurnInInstallError) as exc_info:
            manager.uninstall()
        
        assert 'Uninstaller not found' in str(exc_info.value)
    
    @patch('subprocess.Popen')
    @patch('time.sleep')
    @patch('pathlib.Path.exists')
    @patch.object(BurnInProcessManager, 'is_installed')
    @patch.object(BurnInProcessManager, 'is_running')
    def test_start_process_success(self, mock_is_running, mock_is_installed, 
                                   mock_exists, mock_sleep, mock_popen):
        """Test successful process start."""
        # Setup
        mock_is_installed.return_value = True
        mock_exists.return_value = True
        
        # is_running called twice: once before start (False), once after (True)
        mock_is_running.side_effect = [False, True]
        
        mock_process = Mock()
        mock_process.pid = 1234
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process
        
        manager = BurnInProcessManager("C:\\test")
        
        # Execute
        pid = manager.start_process(script_path="./test.bits")
        
        # Verify
        assert pid == 1234
        assert manager._pid == 1234
        mock_popen.assert_called_once()
    
    @patch.object(BurnInProcessManager, 'is_installed')
    def test_start_process_not_installed(self, mock_is_installed):
        """Test start_process fails when not installed."""
        mock_is_installed.return_value = False
        
        manager = BurnInProcessManager("C:\\test")
        
        with pytest.raises(BurnInProcessError) as exc_info:
            manager.start_process(script_path="./test.bits")
        
        assert 'not installed' in str(exc_info.value)
    
    @patch('pathlib.Path.exists')
    @patch.object(BurnInProcessManager, 'is_installed')
    def test_start_process_script_not_found(self, mock_is_installed, mock_exists):
        """Test start_process fails when script not found."""
        mock_is_installed.return_value = True
        mock_exists.return_value = False
        
        manager = BurnInProcessManager("C:\\test")
        
        with pytest.raises(FileNotFoundError) as exc_info:
            manager.start_process(script_path="./missing.bits")
        
        assert 'Script not found' in str(exc_info.value)
    
    @patch('subprocess.Popen')
    @patch('time.sleep')
    @patch('pathlib.Path.exists')
    @patch.object(BurnInProcessManager, 'is_installed')
    @patch.object(BurnInProcessManager, 'is_running')
    def test_start_process_immediate_termination(self, mock_is_running, mock_is_installed,
                                                 mock_exists, mock_sleep, mock_popen):
        """Test start_process fails when process terminates immediately."""
        mock_is_installed.return_value = True
        mock_exists.return_value = True
        mock_is_running.side_effect = [False, False]  # Not running before, not running after
        
        mock_process = Mock()
        mock_process.pid = 1234
        mock_process.communicate.return_value = (b'', b'Error')
        mock_popen.return_value = mock_process
        
        manager = BurnInProcessManager("C:\\test")
        
        with pytest.raises(BurnInProcessError) as exc_info:
            manager.start_process(script_path="./test.bits")
        
        assert 'terminated immediately' in str(exc_info.value)
    
    def test_stop_process_not_running(self):
        """Test stop_process when process not running."""
        manager = BurnInProcessManager("C:\\test")
        
        result = manager.stop_process()
        
        assert result is True
    
    @patch.object(BurnInProcessManager, 'is_running')
    def test_stop_process_with_subprocess(self, mock_is_running):
        """Test stop_process with subprocess object."""
        mock_is_running.return_value = True
        
        manager = BurnInProcessManager("C:\\test")
        
        # Create mock process
        mock_process = Mock()
        mock_process.terminate = Mock()
        mock_process.wait = Mock()
        manager._process = mock_process
        manager._pid = 1234
        
        result = manager.stop_process()
        
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        assert manager._process is None
        assert manager._pid is None
    
    @patch('psutil.Process')
    @patch.object(BurnInProcessManager, 'is_running')
    def test_stop_process_with_pid_only(self, mock_is_running, mock_psutil_process):
        """Test stop_process with PID only (no subprocess object)."""
        mock_is_running.return_value = True
        
        mock_process = Mock()
        mock_process.terminate = Mock()
        mock_process.wait = Mock()
        mock_psutil_process.return_value = mock_process
        
        manager = BurnInProcessManager("C:\\test")
        manager._pid = 1234
        manager._process = None
        
        result = manager.stop_process()
        
        assert result is True
        mock_process.terminate.assert_called_once()
    
    @patch.object(BurnInProcessManager, 'is_running')
    def test_stop_process_timeout_kill(self, mock_is_running):
        """Test stop_process kills process on timeout."""
        mock_is_running.return_value = True
        
        manager = BurnInProcessManager("C:\\test")
        
        # Create mock process that times out on wait
        mock_process = Mock()
        mock_process.terminate = Mock()
        mock_process.wait = Mock(side_effect=[subprocess.TimeoutExpired(cmd='test', timeout=10), None])
        mock_process.kill = Mock()
        manager._process = mock_process
        
        result = manager.stop_process()
        
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
    
    def test_kill_process_not_running(self):
        """Test kill_process when process not running."""
        manager = BurnInProcessManager("C:\\test")
        
        result = manager.kill_process()
        
        assert result is True
    
    @patch.object(BurnInProcessManager, 'is_running')
    def test_kill_process_with_subprocess(self, mock_is_running):
        """Test kill_process with subprocess object."""
        mock_is_running.return_value = True
        
        manager = BurnInProcessManager("C:\\test")
        
        mock_process = Mock()
        mock_process.kill = Mock()
        mock_process.wait = Mock()
        manager._process = mock_process
        
        result = manager.kill_process()
        
        assert result is True
        mock_process.kill.assert_called_once()
    
    def test_is_running_no_process(self):
        """Test is_running returns False when no process."""
        manager = BurnInProcessManager("C:\\test")
        
        assert manager.is_running() is False
    
    def test_is_running_with_subprocess(self):
        """Test is_running with subprocess object."""
        manager = BurnInProcessManager("C:\\test")
        
        mock_process = Mock()
        mock_process.poll.return_value = None  # Still running
        manager._process = mock_process
        
        assert manager.is_running() is True
        
        # Process terminated
        mock_process.poll.return_value = 0
        assert manager.is_running() is False
    
    @patch('psutil.Process')
    def test_is_running_with_pid_only(self, mock_psutil_process):
        """Test is_running with PID only."""
        mock_process = Mock()
        mock_process.is_running.return_value = True
        mock_psutil_process.return_value = mock_process
        
        manager = BurnInProcessManager("C:\\test")
        manager._pid = 1234
        
        assert manager.is_running() is True
    
    @patch('psutil.Process')
    def test_is_running_process_not_found(self, mock_psutil_process):
        """Test is_running when process not found."""
        mock_psutil_process.side_effect = psutil.NoSuchProcess(1234)
        
        manager = BurnInProcessManager("C:\\test")
        manager._pid = 1234
        
        assert manager.is_running() is False
    
    def test_get_pid_running(self):
        """Test get_pid when process is running."""
        manager = BurnInProcessManager("C:\\test")
        manager._pid = 1234
        manager._process = Mock()
        manager._process.poll.return_value = None
        
        assert manager.get_pid() == 1234
    
    def test_get_pid_not_running(self):
        """Test get_pid when process not running."""
        manager = BurnInProcessManager("C:\\test")
        
        assert manager.get_pid() is None
    
    @patch('psutil.Process')
    @patch.object(BurnInProcessManager, 'is_running')
    def test_get_process_info(self, mock_is_running, mock_psutil_process):
        """Test get_process_info."""
        mock_is_running.return_value = True
        
        mock_process = Mock()
        mock_process.pid = 1234
        mock_process.name.return_value = 'bit.exe'
        mock_process.status.return_value = 'running'
        mock_process.cpu_percent.return_value = 25.5
        
        mock_memory = Mock()
        mock_memory.rss = 100 * 1024 * 1024  # 100 MB
        mock_process.memory_info.return_value = mock_memory
        
        mock_process.num_threads.return_value = 4
        mock_process.create_time.return_value = 1234567890.0
        mock_process.oneshot.return_value.__enter__ = Mock(return_value=None)
        mock_process.oneshot.return_value.__exit__ = Mock(return_value=None)
        
        mock_psutil_process.return_value = mock_process
        
        manager = BurnInProcessManager("C:\\test")
        manager._pid = 1234
        
        info = manager.get_process_info()
        
        assert info is not None
        assert info['pid'] == 1234
        assert info['name'] == 'bit.exe'
        assert info['status'] == 'running'
        assert info['cpu_percent'] == 25.5
        assert info['memory_mb'] == 100.0
        assert info['num_threads'] == 4
    
    @patch.object(BurnInProcessManager, 'is_running')
    def test_get_process_info_not_running(self, mock_is_running):
        """Test get_process_info when process not running."""
        mock_is_running.return_value = False
        
        manager = BurnInProcessManager("C:\\test")
        
        info = manager.get_process_info()
        
        assert info is None
    
    @patch('psutil.process_iter')
    def test_find_existing_process_found(self, mock_process_iter):
        """Test find_existing_process finds matching process."""
        mock_proc1 = Mock()
        mock_proc1.info = {'pid': 999, 'name': 'other.exe', 'exe': 'C:\\other\\other.exe'}
        
        mock_proc2 = Mock()
        mock_proc2.info = {
            'pid': 1234,
            'name': 'bit.exe',
            'exe': 'C:\\test\\bit.exe'
        }
        
        mock_process_iter.return_value = [mock_proc1, mock_proc2]
        
        manager = BurnInProcessManager("C:\\test")
        
        pid = manager.find_existing_process()
        
        assert pid == 1234
    
    @patch('psutil.process_iter')
    def test_find_existing_process_not_found(self, mock_process_iter):
        """Test find_existing_process when no match."""
        mock_proc = Mock()
        mock_proc.info = {'pid': 999, 'name': 'other.exe', 'exe': 'C:\\other\\other.exe'}
        
        mock_process_iter.return_value = [mock_proc]
        
        manager = BurnInProcessManager("C:\\test")
        
        pid = manager.find_existing_process()
        
        assert pid is None
    
    @patch('psutil.Process')
    def test_attach_to_process_success(self, mock_psutil_process):
        """Test attach_to_process."""
        mock_process = Mock()
        mock_process.name.return_value = 'bit.exe'
        mock_psutil_process.return_value = mock_process
        
        manager = BurnInProcessManager("C:\\test", executable_name="bit.exe")
        
        result = manager.attach_to_process(1234)
        
        assert result is True
        assert manager._pid == 1234
        assert manager._process is None
    
    @patch('psutil.Process')
    def test_attach_to_process_wrong_name(self, mock_psutil_process):
        """Test attach_to_process with wrong executable name."""
        mock_process = Mock()
        mock_process.name.return_value = 'other.exe'
        mock_psutil_process.return_value = mock_process
        
        manager = BurnInProcessManager("C:\\test", executable_name="bit.exe")
        
        with pytest.raises(BurnInProcessError) as exc_info:
            manager.attach_to_process(1234)
        
        assert 'not bit.exe' in str(exc_info.value)
    
    @patch('psutil.Process')
    def test_attach_to_process_not_found(self, mock_psutil_process):
        """Test attach_to_process when process not found."""
        mock_psutil_process.side_effect = psutil.NoSuchProcess(1234)
        
        manager = BurnInProcessManager("C:\\test")
        
        with pytest.raises(BurnInProcessError) as exc_info:
            manager.attach_to_process(1234)
        
        assert 'not found' in str(exc_info.value)
