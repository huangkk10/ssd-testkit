"""
OsConfig — MemoryIntegrityAction

Disables Core Isolation / Memory Integrity (Hypervisor-Protected Code
Integrity – HVCI) via its DeviceGuard registry key.

Registry path::

    HKLM\\SYSTEM\\CurrentControlSet\\Control\\DeviceGuard\\Scenarios
        \\HypervisorEnforcedCodeIntegrity\\Enabled

Setting ``Enabled = 0`` disables HVCI.  The change takes effect after reboot.

Mirrors ``disable_memory_integrity()`` in Common.py.
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
from ..registry_helper import write_value, delete_value, read_value_safe, REG_DWORD
from .base_action import AbstractOsAction

logger = get_module_logger(__name__)

_HVCI_KEY  = (
    r"SYSTEM\CurrentControlSet\Control\DeviceGuard"
    r"\Scenarios\HypervisorEnforcedCodeIntegrity"
)
_VAL_ENABLED = "Enabled"
_SNAP_ENABLED = "hvci_enabled_orig"
_CAP_KEY = "memory_integrity"


class MemoryIntegrityAction(AbstractOsAction):
    """
    Disable Core Isolation / Memory Integrity (HVCI).

    Writes ``Enabled = 0`` to the DeviceGuard HVCI scenario registry key.
    The change takes effect after a system reboot.

    Args:
        snapshot_store: Optional shared snapshot dict.
    """

    name = "MemoryIntegrityAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(snapshot_store)

    # ------------------------------------------------------------------ #
    # AbstractOsAction interface                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        """Memory Integrity is available on Win10/11 Pro and Enterprise."""
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """Return ``True`` when ``HypervisorEnforcedCodeIntegrity\\Enabled == 0``."""
        v = read_value_safe("HKLM", _HVCI_KEY, _VAL_ENABLED, default=None)
        # None means the key is absent (HVCI was never explicitly enabled by user)
        # – treat absence as already disabled
        if v is None:
            return True
        return int(v) == 0

    def apply(self) -> None:
        """Set ``Enabled = 0`` to disable Memory Integrity."""
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        orig = read_value_safe("HKLM", _HVCI_KEY, _VAL_ENABLED, default=None)
        self._save_snapshot(_SNAP_ENABLED, orig)
        logger.debug(f"[{self.name}] snapshot: Enabled={orig}")

        write_value("HKLM", _HVCI_KEY, _VAL_ENABLED, 0, REG_DWORD)
        logger.debug(f"[{self.name}] Enabled=0 written (reboot required)")

        self._log_apply_done()

    def revert(self) -> None:
        """Restore the HVCI Enabled value to its pre-apply state."""
        self._log_revert_start()

        orig = self._load_snapshot(_SNAP_ENABLED, default=None)
        if orig is None:
            # Was absent before apply – remove the value we created
            delete_value("HKLM", _HVCI_KEY, _VAL_ENABLED)
            logger.debug(f"[{self.name}] Enabled deleted (was absent before apply)")
        else:
            write_value("HKLM", _HVCI_KEY, _VAL_ENABLED, int(orig), REG_DWORD)
            logger.debug(f"[{self.name}] Enabled restored to {orig}")

        self._log_revert_done()
