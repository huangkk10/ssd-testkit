"""
OsConfig — PagefileAction

Configures the Windows Virtual Memory pagefile via registry.

By default this action disables automatic pagefile management and
configures a fixed-size pagefile on C:\\.  All sizes are in megabytes.

Registry path::

    HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management
        PagingFiles           = ["C:\\pagefile.sys <min_mb> <max_mb>"]
        AutomaticManagedPagefile = 0  (disable automatic management)

``check()`` returns ``True`` when ``AutomaticManagedPagefile == 0`` and the
configured ``PagingFiles`` value matches the requested size.

``revert()`` restores automatic pagefile management.
"""

from __future__ import annotations

import sys
import os
from typing import Optional, Dict, Any, List

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.logger import get_module_logger
from ..os_compat import WindowsBuildInfo, is_supported
from ..registry_helper import (
    write_value, read_value_safe, REG_DWORD, REG_MULTI_SZ,
)
from .base_action import AbstractOsAction

logger = get_module_logger(__name__)

_MM_KEY         = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
_VAL_AUTO       = "AutomaticManagedPagefile"
_VAL_PAGING     = "PagingFiles"
_SNAP_AUTO      = "pagefile_auto_orig"
_SNAP_PAGING    = "pagefile_paging_orig"
_CAP_KEY        = "pagefile"

_DEFAULT_PAGEFILE = r"C:\pagefile.sys"
_DEFAULT_MIN_MB   = 4096
_DEFAULT_MAX_MB   = 8192


class PagefileAction(AbstractOsAction):
    """
    Configure a fixed-size Windows pagefile and disable automatic management.

    Args:
        drive:          Drive letter for the pagefile, e.g. ``"C:"``.
        min_mb:         Minimum pagefile size in MB (default: 4096).
        max_mb:         Maximum pagefile size in MB (default: 8192).
        snapshot_store: Optional shared snapshot dict.
    """

    name = "PagefileAction"

    def __init__(
        self,
        drive: str = "C:",
        min_mb: int = _DEFAULT_MIN_MB,
        max_mb: int = _DEFAULT_MAX_MB,
        snapshot_store: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(snapshot_store)
        self._drive = drive.rstrip("\\")
        self._min_mb = min_mb
        self._max_mb = max_mb
        self._pagefile_path = f"{self._drive}\\pagefile.sys"
        self._paging_entry = f"{self._pagefile_path} {min_mb} {max_mb}"

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """
        Return ``True`` when automatic management is disabled AND the
        configured PagingFiles entry matches the requested size.
        """
        auto = read_value_safe("HKLM", _MM_KEY, _VAL_AUTO, default=None)
        if auto != 0:
            return False
        paging = read_value_safe("HKLM", _MM_KEY, _VAL_PAGING, default=None)
        if paging is None:
            return False
        # PagingFiles is a REG_MULTI_SZ list; look for our entry
        entries = paging if isinstance(paging, list) else [paging]
        return any(self._paging_entry.lower() in str(e).lower() for e in entries)

    def apply(self) -> None:
        """Disable automatic pagefile management and configure fixed size."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        # Snapshot current state
        auto_orig   = read_value_safe("HKLM", _MM_KEY, _VAL_AUTO, default=None)
        paging_orig = read_value_safe("HKLM", _MM_KEY, _VAL_PAGING, default=None)
        self._save_snapshot(_SNAP_AUTO, auto_orig)
        self._save_snapshot(_SNAP_PAGING, paging_orig)

        write_value("HKLM", _MM_KEY, _VAL_AUTO, 0, REG_DWORD)
        write_value("HKLM", _MM_KEY, _VAL_PAGING, [self._paging_entry], REG_MULTI_SZ)
        logger.debug(
            f"[{self.name}] AutomaticManagedPagefile=0, "
            f"PagingFiles={self._paging_entry!r}"
        )

        self._log_apply_done()

    def revert(self) -> None:
        """Restore automatic pagefile management."""
        self._log_revert_start()

        auto_orig   = self._load_snapshot(_SNAP_AUTO, default=None)
        paging_orig = self._load_snapshot(_SNAP_PAGING, default=None)

        # Restore automatic management (default: 1)
        restore_auto = int(auto_orig) if auto_orig is not None else 1
        write_value("HKLM", _MM_KEY, _VAL_AUTO, restore_auto, REG_DWORD)

        if paging_orig is not None:
            paging_list = paging_orig if isinstance(paging_orig, list) else [paging_orig]
            write_value("HKLM", _MM_KEY, _VAL_PAGING, paging_list, REG_MULTI_SZ)
        else:
            # Restore Windows default: system-managed
            write_value("HKLM", _MM_KEY, _VAL_PAGING, [r"C:\pagefile.sys"], REG_MULTI_SZ)

        logger.debug(f"[{self.name}] Pagefile settings restored")
        self._log_revert_done()
