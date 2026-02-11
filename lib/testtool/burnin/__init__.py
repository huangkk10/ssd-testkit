"""
BurnIN Package

This package provides a threading-based controller for managing BurnIN test execution.

Main Components:
- BurnInController: Main controller class inheriting from threading.Thread
- BurnInConfig: Configuration management and validation
- BurnInProcessManager: Process lifecycle management
- BurnInUIMonitor: UI monitoring and interaction
- BurnInScriptGenerator: Test script generation
- Custom exceptions for error handling

Usage:
    from lib.testtool.burnin import BurnInController
    
    # Create and configure controller
    controller = BurnInController(
        install_path="C:\\Program Files\\BurnInTest",
        installer_path="./bin/BurnIn/bitwindows.exe",
        license_path="./bin/BurnIn/key.dat"
    )
    
    # Install BurnIN (if not already installed)
    if not controller.is_installed():
        controller.install()
    
    # Configure test parameters
    controller.set_config(
        test_duration_minutes=60,
        test_drive_letter='D',
        timeout_seconds=7200
    )
    
    # Start test execution
    controller.start()
    
    # Wait for completion
    controller.join(timeout=7200)
    
    # Check result
    if controller.status:
        print("BurnIN test PASSED")
    else:
        print("BurnIN test FAILED")
"""

__version__ = '2.0.0'

# Phase 1-4 exports
from .exceptions import (
    BurnInError,
    BurnInConfigError,
    BurnInTimeoutError,
    BurnInProcessError,
    BurnInInstallError,
    BurnInUIError,
    BurnInTestFailedError,
)

from .config import BurnInConfig
from .script_generator import BurnInScriptGenerator
from .process_manager import BurnInProcessManager
from .ui_monitor import BurnInUIMonitor
from .controller import BurnInController

__all__ = [
    # Exceptions
    'BurnInError',
    'BurnInConfigError',
    'BurnInTimeoutError',
    'BurnInProcessError',
    'BurnInInstallError',
    'BurnInUIError',
    'BurnInTestFailedError',
    # Config
    'BurnInConfig',
    # Script Generator
    'BurnInScriptGenerator',
    # Process Manager
    'BurnInProcessManager',
    # UI Monitor
    'BurnInUIMonitor',
    # Controller (Phase 4)
    'BurnInController',
]
