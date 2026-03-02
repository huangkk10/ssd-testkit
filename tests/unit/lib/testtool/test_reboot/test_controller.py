"""
Unit tests for lib.testtool.reboot.controller.OsRebootController.

All subprocess calls and state-manager interactions are mocked so that
no real reboots are issued and no files are written to disk.

Design note on wait-loop suppression
-------------------------------------
``_issue_reboot()`` calls ``subprocess.run(shutdown /r ...)`` and then enters
a ``time.sleep`` loop waiting for the OS to reboot the process.
In tests we patch ``time.sleep`` to immediately set the stop-event on its
first call, so the loop exits instantly without blocking.  This ensures that
``subprocess.run`` and ``state_manager.save`` are both executed before the
stop-event short-circuits the rest of the method.
"""
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from lib.testtool.reboot.controller import OsRebootController
from lib.testtool.reboot.exceptions import (
    OsRebootConfigError,
    OsRebootProcessError,
    OsRebootStateError,
)


# ------------------------------------------------------------------ #
# Module-level autouse fixtures                                        #
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def patch_state_manager(tmp_path):
    """Replace OsRebootStateManager with a mock for every test in this module."""
    with patch(
        'lib.testtool.reboot.controller.OsRebootStateManager'
    ) as MockSM:
        instance = MockSM.return_value
        # Default: not recovering, state = cycle 0
        instance.is_recovering.return_value = False
        instance.load.return_value = {
            'is_recovering': False,
            'current_cycle':  0,
            'total_cycles':   1,
        }
        instance.save.return_value = None
        instance.clear.return_value = None
        yield instance


@pytest.fixture(autouse=True)
def patch_subprocess():
    """Replace subprocess.run so no real shutdown.exe is called."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ''
    with patch(
        'lib.testtool.reboot.controller.subprocess.run',
        return_value=mock_result,
    ) as mock_run:
        yield mock_run


@pytest.fixture
def ctrl(tmp_path):
    """
    OsRebootController pre-configured with a temp state_file.
    The stop-event is NOT pre-set here; individual tests or the
    ``fast_wait`` fixture are responsible for exiting the wait loop.
    """
    return OsRebootController(
        delay_seconds=0,
        reboot_count=1,
        state_file=str(tmp_path / 'state.json'),
    )


@pytest.fixture
def fast_wait(ctrl):
    """
    Patch ``time.sleep`` so the first call sets the controller stop-event,
    making the post-shutdown wait loop exit immediately.

    Yielded value is the controller so tests can use it directly::

        def test_something(fast_wait):
            fast_wait.start()
            fast_wait.join(timeout=5)
    """
    def _sleep(_secs):
        ctrl._stop_event.set()

    with patch('lib.testtool.reboot.controller.time.sleep', side_effect=_sleep):
        yield ctrl


# ------------------------------------------------------------------ #
# Initialisation                                                       #
# ------------------------------------------------------------------ #

class TestInit:
    def test_status_none_before_start(self, ctrl):
        assert ctrl.status is None

    def test_current_cycle_zero_before_start(self, ctrl):
        assert ctrl.current_cycle == 0

    def test_is_daemon(self, ctrl):
        assert ctrl.daemon is True

    def test_set_config_updates_delay(self, ctrl):
        ctrl.set_config(delay_seconds=30)
        assert ctrl._config['delay_seconds'] == 30

    def test_set_config_invalid_raises(self, ctrl):
        with pytest.raises(OsRebootConfigError):
            ctrl.set_config(reboot_count=0)


# ------------------------------------------------------------------ #
# is_recovering property                                               #
# ------------------------------------------------------------------ #

class TestIsRecovering:
    def test_false_when_state_manager_says_false(self, ctrl, patch_state_manager):
        patch_state_manager.is_recovering.return_value = False
        assert ctrl.is_recovering is False

    def test_true_when_state_manager_says_true(self, ctrl, patch_state_manager):
        patch_state_manager.is_recovering.return_value = True
        assert ctrl.is_recovering is True


# ------------------------------------------------------------------ #
# Fresh-start run                                                      #
# ------------------------------------------------------------------ #

class TestFreshStart:
    def test_issues_shutdown_command(
        self, fast_wait, patch_subprocess, patch_state_manager
    ):
        patch_state_manager.is_recovering.return_value = False
        fast_wait.start()
        fast_wait.join(timeout=5)

        assert patch_subprocess.called
        args = patch_subprocess.call_args[0][0]
        assert args[0] == 'shutdown'
        assert '/r' in args
        assert '/t' in args

    def test_saves_state_before_reboot(
        self, fast_wait, patch_subprocess, patch_state_manager
    ):
        patch_state_manager.is_recovering.return_value = False
        fast_wait.start()
        fast_wait.join(timeout=5)
        patch_state_manager.save.assert_called_once()

    def test_saved_state_has_is_recovering_true(
        self, fast_wait, patch_subprocess, patch_state_manager
    ):
        patch_state_manager.is_recovering.return_value = False
        fast_wait.start()
        fast_wait.join(timeout=5)
        saved = patch_state_manager.save.call_args[0][0]
        assert saved['is_recovering'] is True
        assert saved['current_cycle'] == 1

    def test_status_false_when_stop_set_before_reboot(
        self, ctrl, patch_subprocess, patch_state_manager
    ):
        """Stop event pre-set → reboot skipped → status should be False."""
        patch_state_manager.is_recovering.return_value = False
        ctrl._stop_event.set()
        ctrl.start()
        ctrl.join(timeout=5)
        assert ctrl.status is False
        patch_subprocess.assert_not_called()

    def test_status_false_when_stopped_during_wait(
        self, fast_wait, patch_subprocess, patch_state_manager
    ):
        """Stop fires during the wait loop (after shutdown was issued) → False."""
        patch_state_manager.is_recovering.return_value = False
        fast_wait.start()
        fast_wait.join(timeout=5)
        assert fast_wait.status is False


# ------------------------------------------------------------------ #
# Recovery run — all cycles complete                                   #
# ------------------------------------------------------------------ #

class TestRecoveryAllComplete:
    def test_status_true_when_all_cycles_done(
        self, tmp_path, patch_subprocess, patch_state_manager
    ):
        patch_state_manager.is_recovering.return_value = True
        patch_state_manager.load.return_value = {
            'is_recovering': True,
            'current_cycle':  1,
            'total_cycles':   1,
        }
        c = OsRebootController(
            reboot_count=1,
            state_file=str(tmp_path / 'state.json'),
        )
        c.start()
        c.join(timeout=5)
        assert c.status is True

    def test_state_file_cleared_on_completion(
        self, tmp_path, patch_subprocess, patch_state_manager
    ):
        patch_state_manager.is_recovering.return_value = True
        patch_state_manager.load.return_value = {
            'is_recovering': True,
            'current_cycle':  2,
            'total_cycles':   2,
        }
        c = OsRebootController(
            reboot_count=2,
            state_file=str(tmp_path / 'state.json'),
        )
        c.start()
        c.join(timeout=5)
        patch_state_manager.clear.assert_called_once()

    def test_no_shutdown_issued_when_complete(
        self, tmp_path, patch_subprocess, patch_state_manager
    ):
        patch_state_manager.is_recovering.return_value = True
        patch_state_manager.load.return_value = {
            'is_recovering': True,
            'current_cycle':  3,
            'total_cycles':   3,
        }
        c = OsRebootController(
            reboot_count=3,
            state_file=str(tmp_path / 'state.json'),
        )
        c.start()
        c.join(timeout=5)
        patch_subprocess.assert_not_called()


# ------------------------------------------------------------------ #
# Recovery run — more cycles remain                                    #
# ------------------------------------------------------------------ #

class TestRecoveryMoreCycles:
    def test_issues_another_reboot(
        self, tmp_path, patch_subprocess, patch_state_manager
    ):
        patch_state_manager.is_recovering.return_value = True
        patch_state_manager.load.return_value = {
            'is_recovering': True,
            'current_cycle':  1,
            'total_cycles':   3,
        }
        c = OsRebootController(
            reboot_count=3,
            state_file=str(tmp_path / 'state.json'),
        )

        def _sleep(_):
            c._stop_event.set()

        with patch('lib.testtool.reboot.controller.time.sleep', side_effect=_sleep):
            c.start()
            c.join(timeout=5)

        patch_subprocess.assert_called_once()


# ------------------------------------------------------------------ #
# Error handling                                                        #
# ------------------------------------------------------------------ #

class TestErrorHandling:
    def test_nonzero_exit_code_sets_status_false(
        self, fast_wait, patch_subprocess, patch_state_manager
    ):
        patch_state_manager.is_recovering.return_value = False
        patch_subprocess.return_value.returncode = 1
        patch_subprocess.return_value.stderr = 'Access denied'
        fast_wait.start()
        fast_wait.join(timeout=5)
        assert fast_wait.status is False

    def test_oserror_sets_status_false(
        self, fast_wait, patch_subprocess, patch_state_manager
    ):
        patch_state_manager.is_recovering.return_value = False
        patch_subprocess.side_effect = OSError("shutdown not found")
        fast_wait.start()
        fast_wait.join(timeout=5)
        assert fast_wait.status is False

    def test_state_error_sets_status_false(
        self, fast_wait, patch_subprocess, patch_state_manager
    ):
        patch_state_manager.is_recovering.return_value = False
        patch_state_manager.save.side_effect = OsRebootStateError("disk full")
        fast_wait.start()
        fast_wait.join(timeout=5)
        assert fast_wait.status is False


# ------------------------------------------------------------------ #
# abort_reboot / stop                                                  #
# ------------------------------------------------------------------ #

class TestAbortReboot:
    def test_abort_calls_shutdown_a(self, ctrl, patch_subprocess):
        from unittest.mock import MagicMock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ''
        patch_subprocess.return_value = mock_result

        ctrl.abort_reboot()
        args = patch_subprocess.call_args[0][0]
        assert args == ['shutdown', '/a']

    def test_stop_sets_stop_event(self, ctrl):
        # Reset the stop event first
        ctrl._stop_event.clear()
        with patch.object(ctrl, '_abort_reboot'):
            ctrl.stop()
        assert ctrl._stop_event.is_set()
