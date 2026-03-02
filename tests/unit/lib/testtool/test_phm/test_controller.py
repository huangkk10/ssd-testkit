"""
Unit tests for PHMController.
Tests PHMController with fully mocked dependencies.
"""

from unittest.mock import Mock, patch, MagicMock
import threading

from lib.testtool.phm.controller import PHMController
from lib.testtool.phm.exceptions import (
    PHMConfigError,
    PHMTimeoutError,
    PHMProcessError,
    PHMInstallError,
)
import pytest


class TestPHMController:

    def setup_method(self):
        """Set up minimal valid kwargs for PHMController.__init__."""
        self.valid_kwargs = {
            'cycle_count': 2,
            'timeout': 60,
            'log_path': './testlog/PHMLog',
        }
        # Patch Path.exists to avoid real filesystem checks
        self._patch_exists = patch('pathlib.Path.exists', return_value=True)
        self._patch_exists.start()

    def teardown_method(self):
        self._patch_exists.stop()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def test_init_applies_kwargs(self):
        ctrl = PHMController(**self.valid_kwargs)
        assert ctrl._config['cycle_count'] == 2
        assert ctrl._config['timeout'] == 60

    def test_init_defaults_filled(self):
        ctrl = PHMController(**self.valid_kwargs)
        # Keys not passed should still be present from DEFAULT_CONFIG
        assert 'install_path' in ctrl._config
        assert 'enable_modern_standby' in ctrl._config

    def test_init_status_none(self):
        ctrl = PHMController(**self.valid_kwargs)
        assert ctrl.status is None

    def test_init_error_count_zero(self):
        ctrl = PHMController(**self.valid_kwargs)
        assert ctrl.error_count == 0

    def test_is_thread(self):
        ctrl = PHMController(**self.valid_kwargs)
        assert isinstance(ctrl, threading.Thread)

    def test_is_daemon_thread(self):
        ctrl = PHMController(**self.valid_kwargs)
        assert ctrl.daemon

    def test_init_invalid_key_raises(self):
        with pytest.raises(PHMConfigError):
            PHMController(unknown_param='bad')

    # ------------------------------------------------------------------
    # set_config
    # ------------------------------------------------------------------

    def test_set_config_updates_value(self):
        ctrl = PHMController(**self.valid_kwargs)
        ctrl.set_config(cycle_count=99)
        assert ctrl._config['cycle_count'] == 99

    def test_set_config_invalid_key_raises(self):
        ctrl = PHMController(**self.valid_kwargs)
        with pytest.raises(PHMConfigError):
            ctrl.set_config(bad_key='value')

    # ------------------------------------------------------------------
    # stop
    # ------------------------------------------------------------------

    def test_stop_sets_event(self):
        ctrl = PHMController(**self.valid_kwargs)
        assert not ctrl._stop_event.is_set()
        ctrl.stop()
        assert ctrl._stop_event.is_set()

    # ------------------------------------------------------------------
    # run — mocked _execute_test
    # ------------------------------------------------------------------

    @patch.object(PHMController, '_execute_test')
    def test_run_pass(self, mock_execute):
        """run() sets status=True when _execute_test sets _status=True."""
        def fake_execute(self_ctrl):
            self_ctrl._status = True
        mock_execute.side_effect = lambda: fake_execute(ctrl)

        ctrl = PHMController(**self.valid_kwargs)
        mock_execute.side_effect = None

        def side_effect_set_pass():
            ctrl._status = True

        mock_execute.side_effect = side_effect_set_pass
        ctrl.start()
        ctrl.join(timeout=5)
        assert ctrl.status

    @patch.object(PHMController, '_execute_test')
    def test_run_timeout_sets_false(self, mock_execute):
        mock_execute.side_effect = PHMTimeoutError("timed out")
        ctrl = PHMController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        assert not ctrl.status

    @patch.object(PHMController, '_execute_test')
    def test_run_process_error_sets_false(self, mock_execute):
        mock_execute.side_effect = PHMProcessError("proc failed")
        ctrl = PHMController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        assert not ctrl.status

    @patch.object(PHMController, '_execute_test')
    def test_run_install_error_sets_false(self, mock_execute):
        mock_execute.side_effect = PHMInstallError("install failed")
        ctrl = PHMController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        assert not ctrl.status

    @patch.object(PHMController, '_execute_test')
    def test_run_unexpected_error_sets_false(self, mock_execute):
        mock_execute.side_effect = RuntimeError("unexpected")
        ctrl = PHMController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        assert not ctrl.status

    # ------------------------------------------------------------------
    # is_installed / install helpers
    # ------------------------------------------------------------------

    @patch('lib.testtool.phm.controller.PHMProcessManager')
    def test_is_installed_delegates(self, MockPM):
        mock_pm = MockPM.return_value
        mock_pm.is_installed.return_value = True

        ctrl = PHMController(**self.valid_kwargs)
        ctrl._process_manager = mock_pm

        assert ctrl.is_installed()
        mock_pm.is_installed.assert_called_once()

    @patch('lib.testtool.phm.controller.PHMProcessManager')
    def test_install_raises_when_no_installer_path(self, MockPM):
        ctrl = PHMController(**self.valid_kwargs)
        ctrl._config['installer_path'] = ''
        with pytest.raises(PHMInstallError):
            ctrl.install()


