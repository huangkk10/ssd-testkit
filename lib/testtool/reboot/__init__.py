"""
lib.testtool.reboot — OS Reboot Control Library
================================================

Provides :class:`OsRebootController`, a ``threading.Thread``-based controller
that issues ``shutdown /r /t <n>`` reboot commands and tracks multi-cycle
reboot sequences across OS reboots via a JSON state file.

Quick start::

    from lib.testtool.reboot import OsRebootController

    # Single reboot with 10-second delay (default)
    ctrl = OsRebootController()
    ctrl.start()
    ctrl.join(timeout=60)

    # Three reboots with a 5-second delay each
    ctrl = OsRebootController(
        delay_seconds=5,
        reboot_count=3,
        state_file='./testlog/reboot_state.json',
    )
    ctrl.start()
    ctrl.join(timeout=30)

    # After each reboot, re-create with the same state_file to recover
    ctrl = OsRebootController(state_file='./testlog/reboot_state.json')
    ctrl.start()
    ctrl.join(timeout=30)
    if ctrl.status is True:
        print(f"All {ctrl.current_cycle} reboot(s) completed successfully")

Configuration parameters
------------------------
delay_seconds : int (default 10)
    Seconds passed to ``shutdown /r /t <n>``.  Set to 0 for an immediate reboot.
reboot_count : int (default 1)
    Total number of reboot cycles to perform.
state_file : str (default ``'reboot_state.json'``)
    Path to the JSON persistence file.
abort_on_fail : bool (default True)
    When ``True``, stop the sequence if ``shutdown.exe`` returns a non-zero exit code.

Public API
----------
OsRebootController   Threading controller (main entry point)
OsRebootConfig       Config manager (defaults, validation, merging)
OsRebootStateManager State file reader/writer
OsRebootError        Base exception class (and sub-classes)
"""

from .controller import OsRebootController
from .config import OsRebootConfig
from .state_manager import OsRebootStateManager
from .exceptions import (
    OsRebootError,
    OsRebootConfigError,
    OsRebootTimeoutError,
    OsRebootProcessError,
    OsRebootStateError,
    OsRebootTestFailedError,
)

__all__ = [
    # Main controller
    'OsRebootController',
    # Config
    'OsRebootConfig',
    # State manager
    'OsRebootStateManager',
    # Exceptions
    'OsRebootError',
    'OsRebootConfigError',
    'OsRebootTimeoutError',
    'OsRebootProcessError',
    'OsRebootStateError',
    'OsRebootTestFailedError',
]
