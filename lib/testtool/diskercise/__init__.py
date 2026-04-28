"""
Diskercise Package

Provides a threading-based controller for Diskercise.exe GUI automation.
Supports single-instance and multi-instance (concurrent) operation.

Single-instance usage:
    from lib.testtool.diskercise import DiskerciseController

    ctrl = DiskerciseController(
        exe_path=r'C:\\tools\\Diskercise\\Diskercise.exe'
    )
    ctrl.set_config(thread_count=4, file_size_mb=100, test_duration_minutes=30)
    ctrl.start()
    ctrl.join()
    print('Pass' if ctrl.status else 'Fail')

Multi-instance usage (STC-401 pattern):
    from lib.testtool.diskercise import DiskerciseController

    ctrl = DiskerciseController(
        exe_path=r'C:\\tools\\Diskercise\\Diskercise.exe'
    )
    ctrl.open_instance(dest_folder=r'C:\\1', config={'thread_count': 2})
    ctrl.open_instance(dest_folder=r'C:\\2', config={'thread_count': 2})
    ctrl.start_all_instances()   # click Start on every window
    ctrl.start()                 # begin scan thread
    ctrl.join()
    print('Pass' if ctrl.status else f'Fail: {ctrl.failure_message}')
"""

from .controller import DiskerciseController
from .config import DiskerciseConfig
from .exceptions import (
    DiskerciseError,
    DiskerciseConfigError,
    DiskerciseTimeoutError,
    DiskerciseProcessError,
    DiskerciseUIError,
    DiskerciseTestFailedError,
)

__version__ = '1.0.0'
__all__ = [
    'DiskerciseController',
    'DiskerciseConfig',
    'DiskerciseError',
    'DiskerciseConfigError',
    'DiskerciseTimeoutError',
    'DiskerciseProcessError',
    'DiskerciseUIError',
    'DiskerciseTestFailedError',
]
