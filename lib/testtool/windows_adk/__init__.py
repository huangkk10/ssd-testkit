"""
windows_adk — Windows Assessment Console (WAC) test automation library.

Install / uninstall ADK via ChocoManager before using this library:

    from lib.testtool.choco_manager import ChocoManager
    ChocoManager().install('windows-adk')

Example usage:

    from lib.testtool.windows_adk import ADKController

    ctrl = ADKController(config={"log_path": "./testlog/adk"})
    ctrl.set_assessment("bpfs")
    ctrl.start()
    ctrl.join(timeout=600)
    passed, msg = ctrl.get_result()
    print(passed, msg)
"""

from .controller import ADKController
from .exceptions import (
    ADKConfigError,
    ADKError,
    ADKProcessError,
    ADKResultError,
    ADKTimeoutError,
    ADKUIError,
)

__all__ = [
    "ADKController",
    "ADKError",
    "ADKConfigError",
    "ADKUIError",
    "ADKResultError",
    "ADKTimeoutError",
    "ADKProcessError",
]
