"""
SmiCli Package
==============
Python library wrapper for SmiCli2.exe (SMI Win Tools).

Quick start::

    from lib.testtool.smicli import SmiCliController

    controller = SmiCliController(output_file="./testlog/DUT_Info.ini")
    controller.start()
    controller.join(timeout=90)

    if controller.status:
        print("DUT info collected successfully")
    else:
        print(f"Failed: {controller.error_message}")

Disk type helpers::

    from lib.testtool.smicli import SmiCliController, SmiCliDiskType

    name = SmiCliController.get_disk_type_name(SmiCliDiskType.DISK_TYPE_NVME)
    # -> "NVMe"
"""

from .controller import SmiCliController, SmiCliDiskType, SmiCliProtocolType
from .config import SmiCliConfig
from .exceptions import (
    SmiCliError,
    SmiCliConfigError,
    SmiCliTimeoutError,
    SmiCliProcessError,
    SmiCliTestFailedError,
)

__all__ = [
    # Controller (main entry point)
    "SmiCliController",
    # Domain constants
    "SmiCliDiskType",
    "SmiCliProtocolType",
    # Config
    "SmiCliConfig",
    # Exceptions
    "SmiCliError",
    "SmiCliConfigError",
    "SmiCliTimeoutError",
    "SmiCliProcessError",
    "SmiCliTestFailedError",
]
