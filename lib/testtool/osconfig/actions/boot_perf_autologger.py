"""
OsConfig — BootPerfAutologgerAction

Ensures the ETW AutoLogger session for Boot Performance Diagnostics is set to
start automatically during Fast Startup (hiberboot).

On Windows 11 24H2 (build 26100) the ``Start`` value under the AutoLogger key
defaults to ``0``, which means the tracing session is **not** activated when
the system does a Fast Startup resume.  WAC BPFS assessment reads back boot
trace data after the resume and fails with 0xC0040477
("The system tracing session is not active") when no trace data is present.

On Windows 11 25H2+ the value defaults to ``1`` so this action is a no-op on
those builds (the ``check()`` guard returns True and ``apply()`` skips).

Registry path::

    HKLM\\SYSTEM\\CurrentControlSet\\Control\\WMI\\Autologger\\
        Microsoft-Windows-Boot-Performance-Diagnostics
            Start = 1   (DWORD — enable AutoLogger on next Fast Startup)
            Start = 0   (DWORD — disabled, WAC BPFS will fail)
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
from ..os_compat import WindowsBuildInfo, is_supported
from ..registry_helper import write_value, read_value_safe, REG_DWORD
from .base_action import AbstractOsAction

logger = get_module_logger(__name__)

_AUTOLOGGER_KEY = (
    r"SYSTEM\CurrentControlSet\Control\WMI\Autologger"
    r"\Microsoft-Windows-Boot-Performance-Diagnostics"
)
_VAL_START    = "Start"
_SNAP_KEY     = "boot_perf_autologger_orig"
_CAP_KEY      = "boot_perf_autologger"


class BootPerfAutologgerAction(AbstractOsAction):
    """
    Set ``Start = 1`` on the Boot Performance Diagnostics ETW AutoLogger.

    Required on Windows 11 24H2 where the default is ``0``, causing WAC BPFS
    assessment (Boot Performance Fast Startup) to fail with 0xC0040477.

    The original value is snapshot-ed so ``revert()`` can restore it.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "BootPerfAutologgerAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``Start == 1`` (AutoLogger already enabled)."""
        v = read_value_safe("HKLM", _AUTOLOGGER_KEY, _VAL_START, default=None)
        if v is None:
            return False
        return int(v) == 1

    def apply(self) -> None:
        """Set ``Start = 1`` for the Boot Performance Diagnostics AutoLogger."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _AUTOLOGGER_KEY, _VAL_START, default=None)
        self._save_snapshot(_SNAP_KEY, orig)
        logger.debug(f"[{self.name}] snapshot: {_VAL_START}={orig}")

        write_value("HKLM", _AUTOLOGGER_KEY, _VAL_START, 1, REG_DWORD)
        logger.info(
            f"[{self.name}] {_VAL_START}=1 written to AutoLogger key "
            f"(fixes BPFS 0xC0040477 on Win11 24H2)"
        )

        self._log_apply_done()

    def revert(self) -> None:
        """Restore ``Start`` to its pre-apply value (typically ``0`` on 24H2)."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_KEY, default=None)
        restore = int(orig) if orig is not None else 0
        write_value("HKLM", _AUTOLOGGER_KEY, _VAL_START, restore, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_START} restored to {restore}")

        self._log_revert_done()
