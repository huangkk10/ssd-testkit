"""
Unit tests for PHMProcessManager.
All external I/O (subprocess, winreg, filesystem) is mocked.
"""

from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from lib.testtool.phm.process_manager import PHMProcessManager
from lib.testtool.phm.exceptions import (
    PHMInstallError,
    PHMTimeoutError,
    PHMProcessError,
)
import pytest


class TestPHMProcessManager:

    def setup_method(self):
        self.install_path = 'C:\\Program Files\\Intel\\Powerhouse Mountain'
        self.exe_name = 'PHM.exe'
        self.installer_path = './bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe'

    def _make_manager(self) -> PHMProcessManager:
        return PHMProcessManager(
            install_path=self.install_path,
            executable_name=self.exe_name,
        )

    # ------------------------------------------------------------------
    # is_installed — filesystem path
    # ------------------------------------------------------------------

    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    def test_is_installed_true_when_exe_exists(self, mock_is_file, mock_exists):
        mgr = self._make_manager()
        assert mgr.is_installed()

    @patch('pathlib.Path.exists', return_value=False)
    @patch('lib.testtool.phm.process_manager.winreg')
    def test_is_installed_false_when_no_exe_no_registry(self, mock_winreg, mock_exists):
        mock_winreg.OpenKey.side_effect = OSError
        mock_winreg.HKEY_LOCAL_MACHINE = 0
        mock_winreg.HKEY_CURRENT_USER = 1
        mgr = self._make_manager()
        assert not mgr.is_installed()

    # ------------------------------------------------------------------
    # install
    # ------------------------------------------------------------------

    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('subprocess.run')
    def test_install_success(self, mock_run, mock_is_file, mock_exists):
        mock_run.return_value = Mock(returncode=0, stderr=b'')
        mgr = self._make_manager()
        result = mgr.install(installer_path=self.installer_path)
        assert result
        mock_run.assert_called_once()

    @patch('pathlib.Path.exists', return_value=False)
    def test_install_raises_when_installer_missing(self, mock_exists):
        mgr = self._make_manager()
        with pytest.raises(PHMInstallError, match="Installer not found"):
            mgr.install(installer_path='./missing/installer.exe')

    @patch('pathlib.Path.exists', return_value=True)
    @patch('subprocess.run')
    def test_install_raises_on_nonzero_exit(self, mock_run, mock_exists):
        mock_run.return_value = Mock(returncode=1, stderr=b'Error occurred')
        mgr = self._make_manager()
        with patch('pathlib.Path.is_file', return_value=False):
            with pytest.raises(PHMInstallError):
                mgr.install(installer_path=self.installer_path)

    @patch('pathlib.Path.exists', return_value=True)
    @patch('subprocess.run', side_effect=__import__('subprocess').TimeoutExpired(cmd='inst', timeout=600))
    def test_install_raises_on_timeout(self, mock_run, mock_exists):
        mgr = self._make_manager()
        with pytest.raises(PHMTimeoutError):
            mgr.install(installer_path=self.installer_path)

    # ------------------------------------------------------------------
    # uninstall
    # ------------------------------------------------------------------

    @patch('subprocess.run')
    def test_uninstall_via_exe(self, mock_run):
        mock_run.return_value = Mock(returncode=0)
        mgr = self._make_manager()
        mgr.install_path = Path(self.install_path)

        # Simulate uninstall.exe existing
        with patch('pathlib.Path.exists', return_value=True):
            result = mgr.uninstall()

        assert result

    @patch('pathlib.Path.exists', return_value=False)
    @patch('lib.testtool.phm.process_manager.winreg')
    def test_uninstall_raises_when_no_uninstaller_found(self, mock_winreg, mock_exists):
        mock_winreg.OpenKey.side_effect = OSError
        mock_winreg.HKEY_LOCAL_MACHINE = 0
        mock_winreg.HKEY_CURRENT_USER = 1
        mgr = self._make_manager()
        with pytest.raises(PHMInstallError, match="No PHM uninstaller found"):
            mgr.uninstall()

    # ------------------------------------------------------------------
    # launch
    # ------------------------------------------------------------------

    @patch('pathlib.Path.exists', return_value=True)
    @patch('subprocess.Popen')
    def test_launch_starts_process(self, mock_popen, mock_exists):
        mock_proc = Mock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        mgr = self._make_manager()
        proc = mgr.launch()

        mock_popen.assert_called_once()
        assert mgr.pid == 12345
        self.assertIs(proc, mock_proc)

    @patch('pathlib.Path.exists', return_value=False)
    def test_launch_raises_when_exe_missing(self, mock_exists):
        mgr = self._make_manager()
        with pytest.raises(PHMProcessError, match="executable not found"):
            mgr.launch()

    # ------------------------------------------------------------------
    # terminate
    # ------------------------------------------------------------------

    def test_terminate_no_process(self):
        """terminate() should not raise when no process is tracked."""
        mgr = self._make_manager()
        mgr.terminate()  # should not raise

    @patch('subprocess.Popen')
    def test_terminate_calls_terminate_and_wait(self, mock_popen):
        mock_proc = Mock()
        mock_proc.pid = 999
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        with patch('pathlib.Path.exists', return_value=True):
            mgr = self._make_manager()
            mgr._process = mock_proc
            mgr._pid = 999

        mgr.terminate(timeout=5)
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=5)
        assert mgr.pid is None

    # ------------------------------------------------------------------
    # is_running
    # ------------------------------------------------------------------

    def test_is_running_false_when_no_process(self):
        mgr = self._make_manager()
        assert not mgr.is_running()

    def test_is_running_true_when_process_alive(self):
        mock_proc = Mock()
        mock_proc.poll.return_value = None  # still running

        mgr = self._make_manager()
        mgr._process = mock_proc
        mgr._pid = 1234

        assert mgr.is_running()

    def test_is_running_false_when_process_exited(self):
        mock_proc = Mock()
        mock_proc.poll.return_value = 0  # exited

        mgr = self._make_manager()
        mgr._process = mock_proc
        mgr._pid = 1234

        assert not mgr.is_running()
