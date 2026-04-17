"""
WinPVT Package

Threading-based controller for HP WinPVT test execution with UI automation.

Usage::

    from lib.testtool.winpvt import WinPVTController

    ctrl = WinPVTController(
        exe_path=r'C:\\Program Files\\HP\\WinPVT\\WinPVT.exe',
        result_path='./testlog/WinPVTResult',
        test_category='Standby',
        stress_level='Critical',
        timeout_minutes=120,
    )
    ctrl.start()
    ctrl.join(timeout=ctrl.timeout_seconds + 60)

    if ctrl.status is True:
        print("WinPVT PASSED")
    else:
        raise RuntimeError(ctrl.error_message)
"""

__version__ = '1.0.0'

from .controller import WinPVTController
from .config import WinPVTConfig
from .ui_monitor import WinPVTUIMonitor
from .exceptions import (
    WinPVTError,
    WinPVTConfigError,
    WinPVTTimeoutError,
    WinPVTProcessError,
    WinPVTUIError,
    WinPVTTestFailedError,
)

__all__ = [
    'WinPVTController',
    'WinPVTConfig',
    'WinPVTUIMonitor',
    'WinPVTError',
    'WinPVTConfigError',
    'WinPVTTimeoutError',
    'WinPVTProcessError',
    'WinPVTUIError',
    'WinPVTTestFailedError',
]
