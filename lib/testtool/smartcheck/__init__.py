"""
SmartCheck Package

This package provides a threading-based controller for managing SmartCheck.bat execution.

Main Components:
- SmartCheckController: Main controller class inheriting from threading.Thread
- SmartCheckConfig: Configuration management and validation
- Custom exceptions for error handling

Usage:
    from lib.testtool.smartcheck import SmartCheckController
    
    controller = SmartCheckController(
        bat_path="./bin/SmiWinTools/SmartCheck.bat",
        cfg_ini_path="./bin/SmiWinTools/SmartCheck.ini",
        output_dir="./test_output"
    )
    controller.start()
    controller.join()
    
    if controller.status:
        print("SmartCheck passed")
    else:
        print("SmartCheck failed")
"""

from .controller import SmartCheckController
from .config import SmartCheckConfig
from .exceptions import (
    SmartCheckError,
    SmartCheckConfigError,
    SmartCheckTimeoutError,
    SmartCheckProcessError,
    SmartCheckRunCardError,
)

__version__ = '1.0.0'

__all__ = [
    'SmartCheckController',
    'SmartCheckConfig',
    'SmartCheckError',
    'SmartCheckConfigError',
    'SmartCheckTimeoutError',
    'SmartCheckProcessError',
    'SmartCheckRunCardError',
]
