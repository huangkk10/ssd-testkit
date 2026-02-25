"""
Unit tests for PythonInstallerController.
All external dependencies are mocked — no real installers or file system access.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import threading

from lib.testtool.python_installer.controller import PythonInstallerController
from lib.testtool.python_installer.exceptions import (
    PythonInstallerConfigError,
    PythonInstallerTimeoutError,
    PythonInstallerProcessError,
    PythonInstallerInstallError,
    PythonInstallerTestFailedError,
)


class TestPythonInstallerController(unittest.TestCase):

    def setUp(self):
        """Minimal valid kwargs for __init__ + patch process manager build."""
        self.valid_kwargs = {
            'version': '3.11',
            'timeout_seconds': 60,
        }
        # Prevent real process manager creation during most tests
        self._pm_patcher = patch(
            'lib.testtool.python_installer.controller.PythonInstallerProcessManager',
            autospec=True,
        )
        self.MockPM = self._pm_patcher.start()
        self.mock_pm_instance = self.MockPM.return_value
        self.mock_pm_instance.is_installed.return_value = False
        self.mock_pm_instance.get_executable_path.return_value = 'C:/Python311/python.exe'

    def tearDown(self):
        self._pm_patcher.stop()

    # ----- Initialization -----

    def test_init_sets_version(self):
        ctrl = PythonInstallerController(**self.valid_kwargs)
        self.assertEqual(ctrl._config['version'], '3.11')

    def test_init_status_is_none(self):
        ctrl = PythonInstallerController(**self.valid_kwargs)
        self.assertIsNone(ctrl.status)

    def test_init_error_count_zero(self):
        ctrl = PythonInstallerController(**self.valid_kwargs)
        self.assertEqual(ctrl.error_count, 0)

    def test_is_thread(self):
        ctrl = PythonInstallerController(**self.valid_kwargs)
        self.assertIsInstance(ctrl, threading.Thread)

    def test_is_daemon(self):
        ctrl = PythonInstallerController(**self.valid_kwargs)
        self.assertTrue(ctrl.daemon)

    def test_init_invalid_config_raises(self):
        with self.assertRaises(PythonInstallerConfigError):
            PythonInstallerController(unknown_param='bad')

    # ----- set_config -----

    def test_set_config_updates_version(self):
        ctrl = PythonInstallerController(**self.valid_kwargs)
        ctrl.set_config(version='3.12')
        self.assertEqual(ctrl._config['version'], '3.12')

    def test_set_config_invalid_key_raises(self):
        ctrl = PythonInstallerController(**self.valid_kwargs)
        with self.assertRaises(PythonInstallerConfigError):
            ctrl.set_config(bad_key='value')

    # ----- status property -----

    def test_status_initially_none(self):
        ctrl = PythonInstallerController(**self.valid_kwargs)
        self.assertIsNone(ctrl.status)

    # ----- is_installed -----

    def test_is_installed_delegates_to_pm(self):
        self.mock_pm_instance.is_installed.return_value = True
        ctrl = PythonInstallerController(**self.valid_kwargs)
        self.assertTrue(ctrl.is_installed())

    def test_is_not_installed(self):
        self.mock_pm_instance.is_installed.return_value = False
        ctrl = PythonInstallerController(**self.valid_kwargs)
        self.assertFalse(ctrl.is_installed())

    # ----- stop -----

    def test_stop_sets_event(self):
        ctrl = PythonInstallerController(**self.valid_kwargs)
        self.assertFalse(ctrl._stop_event.is_set())
        ctrl.stop()
        self.assertTrue(ctrl._stop_event.is_set())

    # ----- run — thread execution tests -----

    def test_run_pass(self):
        """run() sets status=True when install succeeds."""
        self.mock_pm_instance.install.return_value = None
        self.mock_pm_instance.get_executable_path.return_value = 'C:/Python311/python.exe'

        ctrl = PythonInstallerController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertTrue(ctrl.status)

    def test_run_install_error(self):
        """run() sets status=False when install raises PythonInstallerInstallError."""
        self.mock_pm_instance.install.side_effect = PythonInstallerInstallError("bad")

        ctrl = PythonInstallerController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertFalse(ctrl.status)
        self.assertEqual(ctrl.error_count, 1)

    def test_run_timeout_error(self):
        """run() sets status=False on PythonInstallerTimeoutError."""
        self.mock_pm_instance.install.side_effect = PythonInstallerTimeoutError("timeout")

        ctrl = PythonInstallerController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertFalse(ctrl.status)

    def test_run_verification_fails_when_exe_not_found(self):
        """run() sets status=False when python.exe not found after install."""
        self.mock_pm_instance.install.return_value = None
        self.mock_pm_instance.get_executable_path.return_value = ''  # not found

        ctrl = PythonInstallerController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertFalse(ctrl.status)

    def test_run_with_uninstall(self):
        """run() calls uninstall when uninstall_after_test=True."""
        self.mock_pm_instance.install.return_value = None
        self.mock_pm_instance.get_executable_path.return_value = 'C:/Python311/python.exe'
        self.mock_pm_instance.uninstall.return_value = None

        ctrl = PythonInstallerController(
            version='3.11',
            timeout_seconds=60,
            uninstall_after_test=True,
        )
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertTrue(ctrl.status)
        self.mock_pm_instance.uninstall.assert_called_once()

    def test_installed_executable_set_after_run(self):
        """installed_executable is populated after successful run."""
        self.mock_pm_instance.install.return_value = None
        self.mock_pm_instance.get_executable_path.return_value = 'C:/Python311/python.exe'

        ctrl = PythonInstallerController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertEqual(ctrl.installed_executable, 'C:/Python311/python.exe')

    def test_stop_before_run_skips_install(self):
        """stop() before run() still completes without error (stop_event set)."""
        ctrl = PythonInstallerController(**self.valid_kwargs)
        ctrl.stop()
        ctrl.start()
        ctrl.join(timeout=5)
        # stop_event was already set, _execute_operation returns early
        self.assertTrue(ctrl.status)
        self.mock_pm_instance.install.assert_not_called()


if __name__ == '__main__':
    unittest.main()
