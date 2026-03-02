"""
PwrTest Package

pwrtest.exe CLI wrapper for OS sleep/resume cycle control and verification.

Drives Windows into a sleep state (S3 / Modern Standby) via the Microsoft WDK
``pwrtest.exe`` tool, monitors the process, and parses the resulting log file to
determine PASS / FAIL.

Main Components:
- PwrTestController : Main controller class (threading.Thread)
- PwrTestConfig     : Configuration management, validation, path resolution
- PwrTestLogParser  : Parser for pwrtestlog.log / pwrtestlog.xml
- Custom exceptions : PwrTestError hierarchy

Usage::

    from lib.testtool.pwrtest import PwrTestController

    ctrl = PwrTestController(
        os_name='win11',
        os_version='25H2',
        cycle_count=1,
        delay_seconds=5,
        wake_after_seconds=30,
        log_path='./testlog/PwrTestLog',
    )
    ctrl.start()
    ctrl.join(timeout=300)

    if ctrl.status:
        print("PwrTest PASSED")
    else:
        print("PwrTest FAILED")
        print(ctrl.result_summary)
"""

from .controller import PwrTestController
from .config import PwrTestConfig, KNOWN_OS_VERSIONS
from .log_parser import PwrTestLogParser, PwrTestTestResult, PwrTestTransitionResult
from .exceptions import (
    PwrTestError,
    PwrTestConfigError,
    PwrTestTimeoutError,
    PwrTestProcessError,
    PwrTestLogParseError,
    PwrTestTestFailedError,
)

__version__ = '1.0.0'

__all__ = [
    'PwrTestController',
    'PwrTestConfig',
    'KNOWN_OS_VERSIONS',
    'PwrTestLogParser',
    'PwrTestTestResult',
    'PwrTestTransitionResult',
    'PwrTestError',
    'PwrTestConfigError',
    'PwrTestTimeoutError',
    'PwrTestProcessError',
    'PwrTestLogParseError',
    'PwrTestTestFailedError',
]
