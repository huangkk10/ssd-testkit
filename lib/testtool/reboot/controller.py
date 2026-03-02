"""
OsReboot Controller

Threading-based controller for issuing ``shutdown /r /t <n>`` reboot commands
and tracking multi-cycle reboot sequences across OS reboots.

The controller is designed to be called in two distinct modes:

1. **Fresh start** (``is_recovering=False``):
   Initialises the state file and issues the first ``shutdown /r /t X`` command.
   The OS reboots and the process terminates.

2. **Recovery** (``is_recovering=True``):
   Called after the OS comes back up.  The controller reads the persisted cycle
   count from the state file, increments it, and either issues the next reboot
   command (if ``current_cycle < reboot_count``) or sets ``status = True`` to
   signal that the full sequence is complete.

Typical usage::

    # Fresh start
    ctrl = OsRebootController(
        delay_seconds=10,
        reboot_count=3,
        state_file='./testlog/reboot_state.json',
    )
    ctrl.start()
    ctrl.join(timeout=60)
    # Process terminates here due to OS reboot

    # --- After each reboot, the test harness re-creates the controller ---
    ctrl = OsRebootController(state_file='./testlog/reboot_state.json')
    ctrl.start()
    ctrl.join(timeout=60)
    print(ctrl.status)          # True once all cycles complete
    print(ctrl.current_cycle)   # e.g. 3
"""

import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from lib.logger import get_module_logger
from .config import OsRebootConfig
from .exceptions import (
    OsRebootConfigError,
    OsRebootError,
    OsRebootProcessError,
    OsRebootStateError,
    OsRebootTestFailedError,
    OsRebootTimeoutError,
)
from .state_manager import OsRebootStateManager

logger = get_module_logger(__name__)


class OsRebootController(threading.Thread):
    """
    Controller for OS reboot cycle testing via ``shutdown /r /t <n>``.

    Inherits from :class:`threading.Thread` — call :meth:`start` to run
    asynchronously, then :meth:`join` to wait for completion.

    On a fresh run the thread body issues a single reboot command and then
    blocks (the OS will reboot the machine).  On recovery the thread body
    checks whether more cycles remain and either issues another reboot or
    marks the sequence as complete.

    Args:
        **kwargs: Any key from :attr:`OsRebootConfig.DEFAULT_CONFIG`.

    Example::

        ctrl = OsRebootController(delay_seconds=5, reboot_count=2)
        ctrl.start()
        ctrl.join(timeout=30)
        print(ctrl.status)          # True = all cycles complete
        print(ctrl.current_cycle)   # number of completed reboots
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(daemon=True)
        self._config: Dict[str, Any] = OsRebootConfig.get_default_config()
        if kwargs:
            self._config = OsRebootConfig.merge_config(self._config, kwargs)

        # State manager handles cross-reboot persistence
        self._state_manager = OsRebootStateManager(self._config['state_file'])

        # Thread control
        self._stop_event = threading.Event()

        # Result state — None while running, True = PASS, False = FAIL
        self._status: Optional[bool] = None
        self._current_cycle: int = 0
        self._error_message: str = ''

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def set_config(self, **kwargs: Any) -> None:
        """
        Update one or more config values at runtime (before :meth:`start`).

        Raises:
            OsRebootConfigError: If an unknown or invalid parameter is given.
        """
        self._config = OsRebootConfig.merge_config(self._config, kwargs)
        # Re-create state manager in case state_file changed
        self._state_manager = OsRebootStateManager(self._config['state_file'])

    @property
    def status(self) -> Optional[bool]:
        """
        Execution status.

        Returns:
            ``None`` while the thread is running,
            ``True`` if all reboot cycles completed successfully,
            ``False`` if an error occurred.
        """
        return self._status

    @property
    def current_cycle(self) -> int:
        """Number of reboot cycles completed so far (updated after each reboot)."""
        return self._current_cycle

    @property
    def is_recovering(self) -> bool:
        """
        ``True`` if the current run is a post-reboot recovery
        (state file exists and ``is_recovering`` flag is set).
        """
        return self._state_manager.is_recovering()

    def stop(self) -> None:
        """
        Signal the controller to stop and cancel any pending reboot.

        Calls ``shutdown /a`` to abort a scheduled reboot if one was issued.
        """
        logger.info("OsRebootController: stop signal received")
        self._stop_event.set()
        self._abort_reboot()

    def abort_reboot(self) -> None:
        """
        Immediately cancel a pending Windows reboot by running ``shutdown /a``.

        This is a public wrapper around the internal :meth:`_abort_reboot` so
        tests and callers can invoke it directly without calling :meth:`stop`.
        """
        self._abort_reboot()

    # ------------------------------------------------------------------ #
    # Thread body                                                          #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Thread entry point — delegates to :meth:`_execute` and captures errors."""
        logger.info("OsRebootController: starting")
        try:
            self._execute()
        except OsRebootTestFailedError as exc:
            logger.error(f"OsRebootController: test FAILED: {exc}")
            self._error_message = str(exc)
            self._status = False
        except OsRebootProcessError as exc:
            logger.error(f"OsRebootController: process error: {exc}")
            self._error_message = str(exc)
            self._status = False
        except OsRebootStateError as exc:
            logger.error(f"OsRebootController: state error: {exc}")
            self._error_message = str(exc)
            self._status = False
        except OsRebootError as exc:
            logger.error(f"OsRebootController: error: {exc}")
            self._error_message = str(exc)
            self._status = False
        except Exception as exc:  # pragma: no cover
            logger.error(
                f"OsRebootController: unexpected error: {exc}", exc_info=True
            )
            self._error_message = str(exc)
            self._status = False

    # ------------------------------------------------------------------ #
    # Internal — execution                                                 #
    # ------------------------------------------------------------------ #

    def _execute(self) -> None:
        """Core logic running inside the thread."""
        reboot_count = self._config['reboot_count']

        if self._state_manager.is_recovering():
            # ── Recovery path ────────────────────────────────────────────
            state = self._state_manager.load()
            self._current_cycle = state.get('current_cycle', 0)
            logger.info(
                f"OsRebootController: recovering — cycle {self._current_cycle}"
                f"/{state.get('total_cycles', reboot_count)}"
            )

            if self._current_cycle >= reboot_count:
                # All cycles done — clean up and report PASS
                logger.info("OsRebootController: all cycles complete — PASS")
                self._state_manager.clear()
                self._status = True
                return

            # More cycles remain — issue the next reboot
            self._issue_reboot()

        else:
            # ── Fresh start path ─────────────────────────────────────────
            logger.info(
                f"OsRebootController: fresh start — "
                f"reboot_count={reboot_count}, delay={self._config['delay_seconds']}s"
            )
            self._current_cycle = 0
            self._issue_reboot()

    def _issue_reboot(self) -> None:
        """
        Persist state, then run ``shutdown /r /t <delay_seconds>``.

        After this call the OS will reboot; this process will be terminated
        by the OS.  The state file ensures the next boot can resume the cycle.
        """
        if self._stop_event.is_set():
            logger.info("OsRebootController: stop event set — skipping reboot")
            self._status = False
            return

        next_cycle = self._current_cycle + 1
        reboot_count = self._config['reboot_count']
        delay = self._config['delay_seconds']

        # Persist state *before* issuing the command so a crash between
        # the save and the reboot can still be recovered.
        state = {
            'is_recovering': True,
            'current_cycle':  next_cycle,
            'total_cycles':   reboot_count,
        }
        self._state_manager.save(state)
        logger.info(
            f"OsRebootController: state saved — "
            f"cycle {next_cycle}/{reboot_count}"
        )

        cmd = ['shutdown', '/r', '/t', str(delay)]
        logger.info(f"OsRebootController: issuing: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise OsRebootProcessError(
                f"Failed to run '{' '.join(cmd)}': {exc}"
            ) from exc

        if result.returncode != 0:
            err_msg = (
                f"shutdown.exe returned exit code {result.returncode}. "
                f"stderr: {result.stderr.strip()}"
            )
            if self._config['abort_on_fail']:
                raise OsRebootProcessError(err_msg)
            else:
                logger.warning(f"OsRebootController: {err_msg} (continuing)")
                return

        logger.info(
            f"OsRebootController: shutdown command accepted — "
            f"system will reboot in {delay}s"
        )

        # Wait for the OS to reboot this process.
        # In production the OS terminates the process here.
        # In unit tests the stop event is set to break out of this wait.
        wait_time = 0.0
        interval  = 0.5
        max_wait  = delay + 60  # generous margin
        while not self._stop_event.is_set() and wait_time < max_wait:
            time.sleep(interval)
            wait_time += interval

        if self._stop_event.is_set():
            logger.info("OsRebootController: stopped while waiting for OS reboot")
            self._status = False
        else:
            # Should not reach here in production
            raise OsRebootTimeoutError(
                f"OS did not reboot within {max_wait}s after shutdown command"
            )

    def _abort_reboot(self) -> None:
        """Run ``shutdown /a`` to cancel a pending scheduled reboot."""
        try:
            result = subprocess.run(
                ['shutdown', '/a'],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info("OsRebootController: scheduled reboot aborted (shutdown /a)")
            else:
                logger.warning(
                    f"OsRebootController: 'shutdown /a' returned "
                    f"{result.returncode}: {result.stderr.strip()}"
                )
        except OSError as exc:
            logger.warning(f"OsRebootController: could not abort reboot: {exc}")
