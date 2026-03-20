"""
PHM (Powerhouse Mountain) Package

Intel Powerhouse Mountain power-cycle test tool automation library.

Provides automated control of PHM for:
- Modern Standby (ACPI S0ix) power cycling tests
- Power Loss Notification (PLN) validation
- SSD endurance verification under power cycling

Main Components:
- PHMController:      Threading controller (start/join/status interface)
- PHMConfig:          Configuration management and validation
- PHMProcessManager:  Install / uninstall / launch / terminate lifecycle
- PHMLogParser:       Parse PHM HTML report files
- PHMUIMonitor:       pywinauto-based UI automation
- Custom exceptions for structured error handling

Usage:
    from lib.testtool.phm import PHMController

    controller = PHMController(
        installer_path='./bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe',
        cycle_count=10,
        enable_modern_standby=True,
        log_path='./testlog/PHMLog',
        timeout=7200,
    )
    controller.start()
    controller.join()

    if controller.status:
        print("PHM PASSED")
    else:
        print(f"PHM FAILED: {controller.error_count} error(s)")

Install-only usage:
    from lib.testtool.choco_manager import ChocoManager

    mgr = ChocoManager()
    if not mgr.is_installed("phm"):
        mgr.install("phm")

Parse log only:
    from lib.testtool.phm import PHMLogParser

    parser = PHMLogParser()
    result = parser.parse_html_report('./testlog/PHMLog/report.html')
    print(result.status, result.completed_cycles, result.errors)
"""

from .controller import PHMController
from .config import PHMConfig
from .log_parser import PHMLogParser, PHMTestResult
from .process_manager import PHMProcessManager
from .visualizer import VisualizerConfig, VisualizerResult, run_visualizer_check
# SleepReportParser and SleepSession are now canonical in lib.testtool.sleepstudy;
# re-exported here for backward compatibility.
from lib.testtool.sleepstudy.sleep_report_parser import SleepReportParser, SleepSession  # noqa: E501
from .pep_checker import PEPChecker, PEPCheckerResult
from .exceptions import (
    PHMError,
    PHMConfigError,
    PHMTimeoutError,
    PHMProcessError,
    PHMInstallError,
    PHMUIError,
    PHMLogParseError,
    PHMTestFailedError,
    PHMSleepReportParseError,
    PHMPEPCheckerError,
)

__version__ = '1.0.0'

__all__ = [
    # Controllers
    'PHMController',
    # Configuration
    'PHMConfig',
    # Log parsing
    'PHMLogParser',
    'PHMTestResult',
    # Sleep study report parsing
    'SleepReportParser',
    'SleepSession',
    # PEPChecker collector
    'PEPChecker',
    'PEPCheckerResult',
    # Process management
    'PHMProcessManager',
    # Visualizer automation
    'VisualizerConfig',
    'VisualizerResult',
    'run_visualizer_check',
    # Exceptions
    'PHMError',
    'PHMConfigError',
    'PHMTimeoutError',
    'PHMProcessError',
    'PHMInstallError',
    'PHMUIError',
    'PHMLogParseError',
    'PHMTestFailedError',
    'PHMSleepReportParseError',
    'PHMPEPCheckerError',
]
