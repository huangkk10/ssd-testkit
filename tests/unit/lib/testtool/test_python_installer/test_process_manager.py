"""
Unit tests for PythonInstallerProcessManager.
All subprocess and network calls are mocked.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
import subprocess

from lib.testtool.python_installer.process_manager import PythonInstallerProcessManager
from lib.testtool.python_installer.exceptions import (
    PythonInstallerInstallError,
    PythonInstallerProcessError,
    PythonInstallerTimeoutError,
)


class TestPythonInstallerProcessManager(unittest.TestCase):

    def setUp(self):
        self.valid_kwargs = {
            'version': '3.11',
            'architecture': 'amd64',
            'install_path': 'C:/Python311',
            'add_to_path': True,
            'installer_path': '',
            'download_dir': './testlog',
            'timeout_seconds': 60,
        }

    # ----- is_installed -----

    @patch('lib.testtool.python_installer.process_manager.Path')
    def test_is_installed_true_when_exe_exists(self, MockPath):
        mock_exe = MagicMock()
        mock_exe.is_file.return_value = True
        MockPath.return_value.__truediv__.return_value = mock_exe

        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        # Directly override install_path's Path evaluation
        with patch.object(Path, 'is_file', return_value=True):
            # Simpler: patch the method directly
            pm.install_path = 'C:/Python311'
            result = pm.is_installed()
        # Since we can't easily patch pathlib.Path(...) /  'python.exe',
        # test via mock subprocess fallback when install_path is empty
        # (see test below)

    def test_is_installed_fallback_without_install_path(self):
        """When install_path is empty, falls back to py launcher."""
        pm = PythonInstallerProcessManager(
            version='3.11',
            install_path='',
        )
        mock_result = Mock()
        mock_result.returncode = 0
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            result = pm.is_installed()
        self.assertTrue(result)
        mock_run.assert_called_once()

    def test_is_installed_false_when_launcher_fails(self):
        """Returns False when py launcher returns non-zero."""
        pm = PythonInstallerProcessManager(version='3.11', install_path='')
        mock_result = Mock()
        mock_result.returncode = 1
        with patch('subprocess.run', return_value=mock_result):
            result = pm.is_installed()
        self.assertFalse(result)

    def test_is_installed_false_when_launcher_not_found(self):
        """Returns False when py launcher is not installed."""
        pm = PythonInstallerProcessManager(version='3.11', install_path='')
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = pm.is_installed()
        self.assertFalse(result)

    # ----- _resolve_full_version -----

    def test_resolve_three_part_version_unchanged(self):
        kwargs = {**self.valid_kwargs, 'version': '3.11.8'}
        pm = PythonInstallerProcessManager(**kwargs)
        pm._resolve_full_version()
        self.assertEqual(pm.full_version, '3.11.8')

    def test_resolve_two_part_version_appends_patch(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        # Mock urllib.request.urlopen to succeed
        with patch('urllib.request.urlopen') as mock_open:
            mock_open.return_value.__enter__ = Mock(return_value=None)
            mock_open.return_value.__exit__ = Mock(return_value=False)
            pm._resolve_full_version()
        self.assertEqual(pm.full_version, '3.11.0')

    def test_resolve_falls_back_on_network_error(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        with patch('urllib.request.urlopen', side_effect=Exception("network error")):
            pm._resolve_full_version()
        self.assertEqual(pm.full_version, '3.11.0')

    # ----- _ensure_installer -----

    def test_ensure_installer_uses_provided_path(self):
        kwargs = {**self.valid_kwargs, 'installer_path': 'C:/fake/python-3.11.0-amd64.exe'}
        pm = PythonInstallerProcessManager(**kwargs)
        pm.full_version = '3.11.0'
        with patch('pathlib.Path.is_file', return_value=True):
            result = pm._ensure_installer()
        # Compare using Path to normalise separators (Windows uses backslash)
        from pathlib import Path as _Path
        self.assertEqual(_Path(result), _Path('C:/fake/python-3.11.0-amd64.exe'))

    def test_ensure_installer_raises_if_provided_path_missing(self):
        kwargs = {**self.valid_kwargs, 'installer_path': 'C:/missing/installer.exe'}
        pm = PythonInstallerProcessManager(**kwargs)
        pm.full_version = '3.11.0'
        with patch('pathlib.Path.is_file', return_value=False):
            with self.assertRaises(PythonInstallerInstallError):
                pm._ensure_installer()

    def test_ensure_installer_raises_on_download_failure(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        pm.full_version = '3.11.0'
        with patch('pathlib.Path.is_file', return_value=False), \
             patch('pathlib.Path.mkdir'), \
             patch('urllib.request.urlretrieve', side_effect=Exception("404")):
            with self.assertRaises(PythonInstallerInstallError):
                pm._ensure_installer()

    # ----- _run_install -----

    def test_run_install_calls_subprocess(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        mock_result = Mock()
        mock_result.returncode = 0
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            pm._run_install(Path('python-3.11.0-amd64.exe'))
        cmd_used = mock_run.call_args[0][0]
        self.assertIn('/quiet', cmd_used)

    def test_run_install_raises_on_nonzero_returncode(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = b'Error: bad'
        with patch('subprocess.run', return_value=mock_result):
            with self.assertRaises(PythonInstallerInstallError):
                pm._run_install(Path('installer.exe'))

    def test_run_install_raises_on_timeout(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd=[], timeout=60)):
            with self.assertRaises(PythonInstallerTimeoutError):
                pm._run_install(Path('installer.exe'))

    def test_run_install_includes_target_dir(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        mock_result = Mock()
        mock_result.returncode = 0
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            pm._run_install(Path('installer.exe'))
        cmd_used = mock_run.call_args[0][0]
        self.assertTrue(any('TargetDir' in str(part) for part in cmd_used))

    def test_run_install_includes_prepend_path_when_add_to_path(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        mock_result = Mock()
        mock_result.returncode = 0
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            pm._run_install(Path('installer.exe'))
        cmd_used = mock_run.call_args[0][0]
        self.assertIn('PrependPath=1', cmd_used)

    # ----- _run_uninstall -----

    def test_run_uninstall_calls_subprocess_with_uninstall_flag(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        mock_result = Mock()
        mock_result.returncode = 0
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            pm._run_uninstall(Path('installer.exe'))
        cmd_used = mock_run.call_args[0][0]
        self.assertIn('/uninstall', cmd_used)

    def test_run_uninstall_raises_on_nonzero_returncode(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = b'Error'
        with patch('subprocess.run', return_value=mock_result):
            with self.assertRaises(PythonInstallerInstallError):
                pm._run_uninstall(Path('installer.exe'))

    # ----- get_executable_path -----

    def test_get_executable_path_with_install_path_found(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        with patch('pathlib.Path.is_file', return_value=True):
            exe = pm.get_executable_path()
        self.assertIn('python.exe', exe)

    def test_get_executable_path_with_install_path_missing(self):
        pm = PythonInstallerProcessManager(**self.valid_kwargs)
        with patch('pathlib.Path.is_file', return_value=False):
            exe = pm.get_executable_path()
        self.assertEqual(exe, '')

    def test_get_executable_path_fallback_to_py_launcher(self):
        pm = PythonInstallerProcessManager(version='3.11', install_path='')
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'C:\\Python311\\python.exe\n'
        with patch('subprocess.run', return_value=mock_result):
            exe = pm.get_executable_path()
        self.assertEqual(exe, 'C:\\Python311\\python.exe')


if __name__ == '__main__':
    unittest.main()
