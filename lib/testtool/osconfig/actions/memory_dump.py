"""
OsConfig — MemoryDumpAction

Enables Small Memory Dump (minidump) on crash, instead of the default
Complete or Kernel memory dump.  Small dumps are faster to write and take
less disk space, making them more suitable for storage test environments.

Registry path::

    HKLM\\SYSTEM\\CurrentControlSet\\Control\\CrashControl
        CrashDumpEnabled = 3   (Small Memory Dump)
        MinidumpDir       = "%SystemRoot%\\Minidump"

Dump type values:
    0 = None
    1 = Complete Memory Dump
    2 = Kernel Memory Dump
    3 = Small Memory Dump  ← target
    7 = Automatic Memory Dump (Win8+)

Mirrors ``enable_small_memory_dump()`` in Common.py.
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
from ..registry_helper import write_value, read_value_safe, REG_DWORD, REG_EXPAND_SZ
from .base_action import AbstractOsAction

logger = get_module_logger(__name__)

_CC_KEY         = r"SYSTEM\CurrentControlSet\Control\CrashControl"
_VAL_DUMP_TYPE  = "CrashDumpEnabled"
_VAL_DUMP_DIR   = "MinidumpDir"
_SMALL_DUMP     = 3
_DEFAULT_DIR    = r"%SystemRoot%\Minidump"
_SNAP_DUMP_TYPE = "memory_dump_type_orig"
_CAP_KEY        = "memory_dump"


class MemoryDumpAction(AbstractOsAction):
    """
    Enable Small Memory Dump (``CrashDumpEnabled = 3``).

    Also ensures ``MinidumpDir`` is set to the default path.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "MemoryDumpAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``CrashDumpEnabled == 3``."""
        v = read_value_safe("HKLM", _CC_KEY, _VAL_DUMP_TYPE, default=None)
        if v is None:
            return False
        return int(v) == _SMALL_DUMP

    def apply(self) -> None:
        """Set CrashDumpEnabled to 3 (Small Memory Dump)."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _CC_KEY, _VAL_DUMP_TYPE, default=None)
        self._save_snapshot(_SNAP_DUMP_TYPE, orig)
        logger.debug(f"[{self.name}] snapshot: {_VAL_DUMP_TYPE}={orig}")

        write_value("HKLM", _CC_KEY, _VAL_DUMP_TYPE, _SMALL_DUMP, REG_DWORD)
        write_value("HKLM", _CC_KEY, _VAL_DUMP_DIR, _DEFAULT_DIR, REG_EXPAND_SZ)
        logger.debug(
            f"[{self.name}] {_VAL_DUMP_TYPE}={_SMALL_DUMP}, "
            f"{_VAL_DUMP_DIR}={_DEFAULT_DIR!r}"
        )

        self._log_apply_done()

    def revert(self) -> None:
        """Restore ``CrashDumpEnabled`` to its pre-apply value."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_DUMP_TYPE, default=None)
        # Default on Win10/11 is 7 (Automatic Memory Dump)
        restore = int(orig) if orig is not None else 7
        write_value("HKLM", _CC_KEY, _VAL_DUMP_TYPE, restore, REG_DWORD)
        logger.debug(f"[{self.name}] {_VAL_DUMP_TYPE} restored to {restore}")

        self._log_revert_done()
