"""
PythonInstaller Package

Handles installation and uninstallation of a specified Python version on Windows.
Supports configurable version, architecture, install path, and PATH registration.

Main Components:
- PythonInstallerController: Main controller (threading.Thread)
- PythonInstallerConfig:     Configuration management and validation
- PythonInstallerProcessManager: Download / install / uninstall lifecycle
- Custom exceptions for error handling

Usage — install Python 3.11::

    from lib.testtool.python_installer import PythonInstallerController

    controller = PythonInstallerController(version='3.11')
    controller.start()
    controller.join(timeout=300)

    if controller.status:
        print("Installed at:", controller.installed_executable)
    else:
        print("Install failed")

Usage — install then uninstall::

    controller = PythonInstallerController(
        version='3.11',
        install_path='C:/Python311_test',
        uninstall_after_test=True,
    )
    controller.start()
    controller.join(timeout=600)
    assert controller.status is True

Usage — synchronous / blocking::

    from lib.testtool.python_installer import PythonInstallerController

    ctrl = PythonInstallerController(version='3.11')
    ctrl.install()           # blocking, raises on failure
    print(ctrl.installed_executable)
    ctrl.uninstall()         # optional cleanup
"""

from .controller import PythonInstallerController
from .config import PythonInstallerConfig
from .process_manager import PythonInstallerProcessManager
from .exceptions import (
    PythonInstallerError,
    PythonInstallerConfigError,
    PythonInstallerTimeoutError,
    PythonInstallerProcessError,
    PythonInstallerInstallError,
    PythonInstallerVersionError,
    PythonInstallerTestFailedError,
)

__version__ = '1.0.0'

__all__ = [
    'PythonInstallerController',
    'PythonInstallerConfig',
    'PythonInstallerProcessManager',
    'PythonInstallerError',
    'PythonInstallerConfigError',
    'PythonInstallerTimeoutError',
    'PythonInstallerProcessError',
    'PythonInstallerInstallError',
    'PythonInstallerVersionError',
    'PythonInstallerTestFailedError',
]
