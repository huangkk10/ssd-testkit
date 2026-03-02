"""
OsConfig — TelemetryAction

Disables the Connected User Experiences and Telemetry service (DiagTrack),
which collects Windows diagnostic data. Disabling it reduces background
network traffic during SSD endurance / performance tests.

Service: DiagTrack
Registry key: HKLM\\SYSTEM\\CurrentControlSet\\Services\\DiagTrack

Additional registry setting applied in ``apply()`` to suppress telemetry
data collection::

    HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection
        AllowTelemetry = 0  (REG_DWORD)
"""

from __future__ import annotations

import sys
import os
from typing import Optional, Dict, Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.logger import get_module_logger
from ..registry_helper import (
    write_value, delete_value, read_value_safe, REG_DWORD
)
from ..os_compat import WindowsBuildInfo
from ._base_service_action import BaseServiceAction

logger = get_module_logger(__name__)

_TELEMETRY_KEY  = r"SOFTWARE\Policies\Microsoft\Windows\DataCollection"
_TELEMETRY_VAL  = "AllowTelemetry"
_SNAP_TELEMETRY = "allow_telemetry_orig"


class TelemetryAction(BaseServiceAction):
    """
    Disable DiagTrack service and set AllowTelemetry GPO to 0.

    Extends :class:`BaseServiceAction` to also write the
    ``AllowTelemetry`` Group Policy registry value.
    """

    name = "TelemetryAction"
    service_name = "DiagTrack"
    capability_key = "telemetry"

    def apply(self) -> None:
        # Snapshot telemetry policy value
        orig = read_value_safe("HKLM", _TELEMETRY_KEY, _TELEMETRY_VAL, default=None)
        self._save_snapshot(_SNAP_TELEMETRY, orig)

        write_value("HKLM", _TELEMETRY_KEY, _TELEMETRY_VAL, 0, REG_DWORD)
        logger.debug(f"[{self.name}] AllowTelemetry set to 0")

        super().apply()

    def revert(self) -> None:
        super().revert()

        orig = self._load_snapshot(_SNAP_TELEMETRY, default=None)
        if orig is not None:
            write_value("HKLM", _TELEMETRY_KEY, _TELEMETRY_VAL, int(orig), REG_DWORD)
            logger.debug(f"[{self.name}] AllowTelemetry restored to {orig}")
        else:
            delete_value("HKLM", _TELEMETRY_KEY, _TELEMETRY_VAL)
            logger.debug(f"[{self.name}] AllowTelemetry deleted (was absent)")
