"""
OsConfig Base Service Action

Shared base class for all Windows service disable/enable actions.

Every concrete service action (SearchIndex, SysMain, WindowsUpdate, etc.)
inherits from :class:`BaseServiceAction` and only needs to declare three
class attributes::

    class SearchIndexAction(BaseServiceAction):
        name            = "SearchIndexAction"
        service_name    = "WSearch"
        capability_key  = "search_index"

Disable pattern
---------------
1. ``apply()`` – snapshots current start-type + running state, then:
   - ``sc stop <service>``     (ignore rc if already stopped)
   - ``sc config <service> start=disabled``
2. ``check()`` – service Start registry value == 4 (Disabled)
3. ``revert()`` – restores original start-type, re-starts if was running

Service Start registry values (HKLM\\SYSTEM\\CurrentControlSet\\Services\\<name>\\Start)::

    0 = Boot      → sc start= boot
    1 = System    → sc start= system
    2 = Automatic → sc start= auto
    3 = Manual    → sc start= demand
    4 = Disabled  → sc start= disabled
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
from ..os_compat import WindowsBuildInfo, is_supported, CAPABILITIES
from ..registry_helper import read_value_safe, REG_DWORD
from ..exceptions import OsConfigActionError, OsConfigNotSupportedError
from .base_action import AbstractOsAction
from ._helpers import run_command, run_command_with_output

logger = get_module_logger(__name__)

# Registry start-type → sc config start= argument mapping
_START_TYPE_TO_SC: Dict[int, str] = {
    0: "boot",
    1: "system",
    2: "auto",
    3: "demand",
    4: "disabled",
}

# Services registry base key
_SERVICES_KEY = r"SYSTEM\CurrentControlSet\Services"

# Snapshot keys
_SNAP_START_TYPE = "start_type"
_SNAP_WAS_RUNNING = "was_running"


def _get_service_start_type(service_name: str) -> Optional[int]:
    """
    Read the Start registry value for *service_name*.

    Returns the integer start type (0–4) or ``None`` if the service key
    doesn't exist (service not installed).
    """
    key_path = rf"{_SERVICES_KEY}\{service_name}"
    value = read_value_safe("HKLM", key_path, "Start", default=None)
    return int(value) if value is not None else None


def _get_service_state(service_name: str) -> str:
    """
    Return the current state of *service_name* as an uppercase string.

    Possible return values: ``"RUNNING"``, ``"STOPPED"``,
    ``"STOP_PENDING"``, ``"START_PENDING"``, ``"NOT_FOUND"``, ``"UNKNOWN"``.
    """
    rc, stdout, _ = run_command_with_output(f"sc query {service_name}")
    if rc == 1060:
        return "NOT_FOUND"
    stdout_upper = stdout.upper()
    for state in ("RUNNING", "STOPPED", "STOP_PENDING", "START_PENDING",
                  "PAUSED", "PAUSE_PENDING", "CONTINUE_PENDING"):
        if state in stdout_upper:
            return state
    return "UNKNOWN"


def _sc_start_type_arg(start_type: int) -> str:
    """Convert an integer start-type to the ``sc config start=`` argument string."""
    return _START_TYPE_TO_SC.get(start_type, "demand")


class BaseServiceAction(AbstractOsAction):
    """
    Base class for service disable/enable actions.

    Subclasses must define:
    - :attr:`name`           – display name for logs
    - :attr:`service_name`   – Windows service name (e.g. ``"WSearch"``)
    - :attr:`capability_key` – key in :data:`~lib.testtool.osconfig.os_compat.CAPABILITIES`
    """

    #: Override in each subclass.
    name: str = "BaseServiceAction"
    #: Windows service name (e.g. ``"WSearch"``).  Override in subclass.
    service_name: str = ""
    #: Capability key in CAPABILITIES dict.  Override in subclass.
    capability_key: str = ""

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)
        if not self.service_name:
            raise ValueError(f"{self.__class__.__name__}: service_name must be set")

    # ------------------------------------------------------------------ #
    # AbstractOsAction interface                                           #
    # ------------------------------------------------------------------ #

    def apply(self) -> None:
        """Disable the service (stop + set start type to Disabled)."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        # Snapshot current state before making changes
        current_start_type = _get_service_start_type(self.service_name)
        current_state = _get_service_state(self.service_name)
        was_running = current_state == "RUNNING"

        self._save_snapshot(_SNAP_START_TYPE, current_start_type)
        self._save_snapshot(_SNAP_WAS_RUNNING, was_running)

        logger.debug(
            f"[{self.name}] snapshot: start_type={current_start_type}, "
            f"was_running={was_running}"
        )

        # Stop service (ignore errors – may already be stopped / not exist)
        rc_stop = run_command(f"sc stop {self.service_name}")
        if rc_stop not in (0, 1062, 1060):  # 1062=not started, 1060=not found
            logger.warning(
                f"[{self.name}] sc stop returned rc={rc_stop} – continuing anyway"
            )

        # Disable start type
        rc_cfg = run_command(f"sc config {self.service_name} start=disabled")
        if rc_cfg not in (0,):
            raise OsConfigActionError(
                f"{self.name}: sc config {self.service_name} start=disabled "
                f"returned rc={rc_cfg}"
            )

        self._log_apply_done()

    def revert(self) -> None:
        """Restore the service to its pre-apply start type and running state."""
        self._log_revert_start()

        original_start_type = self._load_snapshot(_SNAP_START_TYPE, default=None)
        was_running = self._load_snapshot(_SNAP_WAS_RUNNING, default=None)

        if original_start_type is None:
            self._log_revert_skip()
            return

        sc_type_arg = _sc_start_type_arg(original_start_type)
        rc_cfg = run_command(f"sc config {self.service_name} start={sc_type_arg}")
        if rc_cfg not in (0,):
            logger.warning(
                f"[{self.name}] sc config start={sc_type_arg} returned rc={rc_cfg}"
            )

        if was_running:
            rc_start = run_command(f"sc start {self.service_name}")
            if rc_start not in (0, 1056):  # 1056=already running
                logger.warning(
                    f"[{self.name}] sc start returned rc={rc_start}"
                )

        self._log_revert_done()

    def check(self) -> bool:
        """
        Return ``True`` when the service start type is Disabled (4).

        Uses the registry value directly – faster than parsing sc output.
        Returns ``True`` also when the service is not found (start_type is None),
        since a missing service cannot run.
        """
        start_type = _get_service_start_type(self.service_name)
        if start_type is None:
            logger.debug(
                f"[{self.name}] service '{self.service_name}' not found "
                "– treating as already disabled"
            )
            return True
        return start_type == 4  # 4 = Disabled

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        """
        Return ``True`` if this service action is supported on *build_info*.

        Falls back to ``True`` when no ``capability_key`` is defined (i.e.
        for subclasses that skip the capability check).
        """
        if not cls.capability_key:
            return True
        try:
            return is_supported(cls.capability_key, build_info)
        except KeyError:
            return True
