"""
CDI (CrystalDiskInfo) Package

Wraps CrystalDiskInfo (DiskInfo64.exe) for automated disk-health data
collection: exports the text report, parses SMART attributes to JSON,
and captures per-drive screenshots via pywinauto.

Main Components:
- CDIController:  Main controller class (threading.Thread), orchestrates
                  the full monitoring workflow.
- CDIConfig:      Configuration management and validation.
- CDILogParser:   Parses DiskInfo.txt into a structured dict / JSON file.
- CDIUIMonitor:   pywinauto wrapper for UI interactions.
- Custom exceptions for granular error handling.

Usage:
    from lib.testtool.cdi import CDIController

    controller = CDIController(
        executable_path='./bin/CrystalDiskInfo/DiskInfo64.exe',
        log_path='./testlog',
        log_prefix='Before_',
        screenshot_drive_letter='C:',
    )
    controller.start()
    controller.join(timeout=300)

    if controller.status:
        print('CDI workflow PASSED')
    else:
        print('CDI workflow FAILED')

    # SMART comparison after two snapshots
    ok, msg = controller.compare_smart_value_no_increase(
        'C:', 'Before_', 'After_', ['Unsafe Shutdowns', 'Power Cycles']
    )
    if not ok:
        raise Exception(msg)
"""

from .controller import CDIController, CDILogParser
from .config import CDIConfig
from .exceptions import (
    CDIError,
    CDIConfigError,
    CDITimeoutError,
    CDIProcessError,
    CDIUIError,
    CDITestFailedError,
)
from .ui_monitor import CDIUIMonitor

__version__ = '1.0.0'

__all__ = [
    'CDIController',
    'CDILogParser',
    'CDIConfig',
    'CDIUIMonitor',
    'CDIError',
    'CDIConfigError',
    'CDITimeoutError',
    'CDIProcessError',
    'CDIUIError',
    'CDITestFailedError',
]
