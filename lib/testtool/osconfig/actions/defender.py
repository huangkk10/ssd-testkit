"""
OsConfig — DefenderAction

Disables Windows Defender Real-time Monitoring using a two-tier approach:

1. **PowerShell** ``Set-MpPreference -DisableRealtimeMonitoring $true``
   (works on builds before Tamper Protection is active or when TP is disabled).
2. **Registry fallback** ``HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender``
   ``DisableAntiSpyware = 1``  (GPO path; effective even when PowerShell is
   blocked by Tamper Protection on some configurations).

If both attempts fail (e.g. Tamper Protection fully enforced), a **warning**
is logged but no exception is raised, so a multi-action controller run is not
interrupted.

Tamper Protection awareness
---------------------------
On Windows 10 1903+ (Build ≥ 18362) Microsoft enabled Tamper Protection by
default.  Disabling Defender in a test-lab environment typically requires:

* Disabling Tamper Protection first via the Security Center UI, *or*
* Running as a managed/MDM device with a policy that allows it, *or*
* Using the Windows Security Center COM API (not exposed in a stable SDK).

This action records whether the PowerShell command succeeded so that
``check()`` and ``revert()`` can choose the most accurate path.
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
from ..exceptions import OsConfigActionError
from .base_action import AbstractOsAction
from ._helpers import run_powershell

logger = get_module_logger(__name__)

# GPO registry path (works even on Home without gpedit)
_DEF_KEY      = r"SOFTWARE\Policies\Microsoft\Windows Defender"
_VAL_DISABLE  = "DisableAntiSpyware"
_SNAP_REG     = "defender_disable_antispyware_orig"
_SNAP_PS_OK   = "defender_ps_succeeded"

_CAP_KEY = "defender_realtime"


class DefenderAction(AbstractOsAction):
    """
    Disable Windows Defender Real-time Monitoring.

    Attempts PowerShell first, then falls back to a registry GPO value.
    On failure, logs a warning rather than raising, to avoid blocking test
    runs on machines where Tamper Protection cannot be programmatically
    disabled.

    Args:
        snapshot_store:      Optional shared snapshot dict.
        fail_on_error:       If ``True``, raise
            :class:`~lib.testtool.osconfig.exceptions.OsConfigActionError`
            when both PowerShell and registry writes fail.  Default: ``False``.
    """

    name = "DefenderAction"

    def __init__(
        self,
        snapshot_store: Optional[Dict[str, Any]] = None,
        fail_on_error: bool = False,
    ) -> None:
        super().__init__(snapshot_store)
        self._fail_on_error = fail_on_error

    # ------------------------------------------------------------------ #
    # AbstractOsAction interface                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        """Defender Real-time Monitoring is available on all supported builds."""
        return is_supported(_CAP_KEY, build_info)

    def check(self) -> bool:
        """
        Return ``True`` when the registry GPO value ``DisableAntiSpyware == 1``.

        Note: This does not query ``Get-MpPreference`` at runtime to keep the
        check fast and side-effect-free.  The registry GPO value is the
        authoritative source for the policy setting.
        """
        v = read_value_safe("HKLM", _DEF_KEY, _VAL_DISABLE, default=None)
        return v == 1

    def apply(self) -> None:
        """
        Disable Defender via PowerShell; fall back to registry if PowerShell fails.
        """
        self._log_apply_start()

        if self.check():
            self._log_apply_skip()
            return

        # Snapshot registry value
        reg_orig = read_value_safe("HKLM", _DEF_KEY, _VAL_DISABLE, default=None)
        self._save_snapshot(_SNAP_REG, reg_orig)

        # ── Tier 1: PowerShell ──────────────────────────────────────────
        ps_cmd = "Set-MpPreference -DisableRealtimeMonitoring $true"
        ps_rc = run_powershell(ps_cmd)
        ps_ok = (ps_rc == 0)
        self._save_snapshot(_SNAP_PS_OK, ps_ok)

        if ps_ok:
            logger.debug(f"[{self.name}] PowerShell Set-MpPreference succeeded")
        else:
            logger.warning(
                f"[{self.name}] PowerShell Set-MpPreference returned rc={ps_rc} "
                "– falling back to registry GPO"
            )

        # ── Tier 2: Registry GPO ────────────────────────────────────────
        try:
            write_value("HKLM", _DEF_KEY, _VAL_DISABLE, 1, REG_DWORD)
            logger.debug(f"[{self.name}] registry GPO {_VAL_DISABLE}=1 written")
        except Exception as exc:
            msg = f"[{self.name}] registry fallback failed: {exc}"
            if self._fail_on_error and not ps_ok:
                raise OsConfigActionError(msg) from exc
            logger.warning(msg)

        self._log_apply_done()

    def revert(self) -> None:
        """Restore Defender Real-time Monitoring to its pre-apply state."""
        self._log_revert_start()

        reg_orig = self._load_snapshot(_SNAP_REG, default=None)
        ps_ok    = self._load_snapshot(_SNAP_PS_OK, default=False)

        # Restore PowerShell state if it was successfully disabled via PS
        if ps_ok:
            ps_rc = run_powershell("Set-MpPreference -DisableRealtimeMonitoring $false")
            if ps_rc != 0:
                logger.warning(
                    f"[{self.name}] PowerShell revert returned rc={ps_rc}"
                )
            else:
                logger.debug(f"[{self.name}] PowerShell revert succeeded")

        # Restore registry GPO value
        if reg_orig is not None:
            write_value("HKLM", _DEF_KEY, _VAL_DISABLE, int(reg_orig), REG_DWORD)
            logger.debug(f"[{self.name}] {_VAL_DISABLE} restored to {reg_orig}")
        else:
            delete_value("HKLM", _DEF_KEY, _VAL_DISABLE)
            logger.debug(f"[{self.name}] {_VAL_DISABLE} deleted (was absent)")

        self._log_revert_done()
