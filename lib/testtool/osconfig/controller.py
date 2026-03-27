"""
OsConfig — OsConfigController

Orchestrates all OS configuration actions based on an
:class:`~lib.testtool.osconfig.config.OsConfigProfile`.

Responsibilities:
  - Build the action list from the profile
  - Skip actions not supported on the current build (warn or raise)
  - Delegate ``apply_all()`` / ``revert_all()`` / ``check_all()`` to each action
  - Optionally persist the snapshot via :class:`OsConfigStateManager`

Usage::

    from lib.testtool.osconfig import OsConfigController, OsConfigProfile

    profile = OsConfigProfile.default()
    controller = OsConfigController(profile=profile)

    controller.apply_all()     # apply & snapshot originals
    # ... run storage tests ...
    controller.revert_all()    # restore every original value

    # Inspect current state without changing anything:
    status = controller.check_all()  # → {"SearchIndexAction": False, ...}
"""

from __future__ import annotations

import sys
import os
from typing import Dict, List, Optional, Tuple, Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.logger import get_module_logger
from .config import OsConfigProfile
from .exceptions import OsConfigNotSupportedError, OsConfigActionError
from .os_compat import get_build_info, WindowsBuildInfo
from .state_manager import OsConfigStateManager
from .actions import (
    AbstractOsAction,
    # ── Phase 2: Services ────────────────────────────────────────────────
    SearchIndexAction,
    SysMainAction,
    WindowsUpdateAction,
    WerAction,
    TelemetryAction,
    PcaSvcAction,
    # ── Phase 3: OneDrive + Security ─────────────────────────────────────
    OneDriveAction,
    DefenderAction,
    MemoryIntegrityAction,
    VulnDriverBlocklistAction,
    FirewallAction,
    UacAction,
    # ── Phase 4: Boot ────────────────────────────────────────────────────
    TestSigningAction,    DisableTestSigningAction,    RecoveryAction,
    AutoRebootAction,
    AutoAdminLogonAction,
    MemoryDumpAction,
    # ── Phase 4: Power ────────────────────────────────────────────────────
    PowerPlanAction,
    PowerTimeoutAction,
    HibernationAction,
    UnattendedSleepAction,
    # ── Phase 4: Schedule ─────────────────────────────────────────────────
    DefragScheduleAction,
    DefenderScanScheduleAction,
    EdgeUpdateTasksAction,
    OneDriveTasksAction,
    MemoryDiagnosticTasksAction,
    McAfeeTasksAction,
    # ── Phase 4: System ───────────────────────────────────────────────────
    SystemRestoreAction,
    FastStartupAction,
    NotificationAction,
    CortanaAction,
    BackgroundAppsAction,
    PagefileAction,
)

logger = get_module_logger(__name__)


def _build_action_list(
    profile: OsConfigProfile,
    snapshot_store: Dict[str, Any],
) -> List[AbstractOsAction]:
    """
    Translate *profile* into an ordered list of action instances.

    All actions share the same *snapshot_store* dict so that the controller
    can persist / restore a single consolidated snapshot.
    """
    actions: List[AbstractOsAction] = []
    s = snapshot_store   # shorthand

    # ── Services ──────────────────────────────────────────────────────────
    if profile.disable_search_index:
        actions.append(SearchIndexAction(snapshot_store=s))
    if profile.disable_sysmain:
        actions.append(SysMainAction(snapshot_store=s))
    if profile.disable_windows_update:
        actions.append(WindowsUpdateAction(snapshot_store=s))
    if profile.disable_wer:
        actions.append(WerAction(snapshot_store=s))
    if profile.disable_telemetry:
        actions.append(TelemetryAction(snapshot_store=s))
    if profile.disable_pcasvc:
        actions.append(PcaSvcAction(snapshot_store=s))

    # ── OneDrive + Security ────────────────────────────────────────────────
    if profile.disable_onedrive:
        actions.append(OneDriveAction(snapshot_store=s))
    if profile.disable_defender:
        actions.append(DefenderAction(snapshot_store=s))
    if profile.disable_memory_integrity:
        actions.append(MemoryIntegrityAction(snapshot_store=s))
    if profile.disable_vuln_driver_blocklist:
        actions.append(VulnDriverBlocklistAction(snapshot_store=s))
    if profile.disable_firewall:
        actions.append(FirewallAction(snapshot_store=s))
    if profile.disable_uac:
        actions.append(UacAction(snapshot_store=s))

    # ── Boot ──────────────────────────────────────────────────────────────
    if profile.enable_test_signing:
        actions.append(TestSigningAction(snapshot_store=s))
    if profile.disable_test_signing:
        actions.append(DisableTestSigningAction(snapshot_store=s))
    if profile.disable_recovery:
        actions.append(RecoveryAction(snapshot_store=s))
    if profile.disable_auto_reboot:
        actions.append(AutoRebootAction(snapshot_store=s))
    if profile.enable_auto_admin_logon:
        import getpass as _getpass
        _username = profile.auto_login_username or _getpass.getuser()
        _password = (
            profile.auto_login_password
            or os.getenv("SSD_TESTKIT_AUTO_LOGIN_PASSWORD", "")
        )
        if not _password:
            raise OsConfigActionError(
                "enable_auto_admin_logon requires a password. "
                "Set 'auto_login_password' in osconfig.yaml or the "
                "SSD_TESTKIT_AUTO_LOGIN_PASSWORD environment variable."
            )
        _domain = profile.auto_login_domain or "."
        logger.debug(
            "[OsConfigController] AutoAdminLogon: username=%r  domain=%r  password=<redacted>",
            _username, _domain,
        )
        actions.append(AutoAdminLogonAction(
            username=_username,
            password=_password,
            domain=_domain,
            snapshot_store=s,
        ))
    if profile.set_small_memory_dump:
        actions.append(MemoryDumpAction(snapshot_store=s))

    # ── Power ──────────────────────────────────────────────────────────────
    if profile.power_plan:
        actions.append(PowerPlanAction(plan=profile.power_plan, snapshot_store=s))
    if profile.disable_monitor_timeout:
        actions.append(PowerTimeoutAction("monitor", snapshot_store=s))
    if profile.disable_standby_timeout:
        actions.append(PowerTimeoutAction("standby", snapshot_store=s))
    if profile.disable_hibernate_timeout:
        actions.append(PowerTimeoutAction("hibernate", snapshot_store=s))
    if profile.disable_disk_timeout:
        actions.append(PowerTimeoutAction("disk", snapshot_store=s))
    if profile.disable_hibernation:
        actions.append(HibernationAction(snapshot_store=s))
    if profile.disable_unattended_sleep:
        actions.append(UnattendedSleepAction(snapshot_store=s))

    # ── Schedule ──────────────────────────────────────────────────────────
    if profile.disable_defrag_schedule:
        actions.append(DefragScheduleAction(snapshot_store=s))
    if profile.disable_defender_scan_schedule:
        actions.append(DefenderScanScheduleAction(snapshot_store=s))
    if profile.disable_edge_update_tasks:
        actions.append(EdgeUpdateTasksAction(snapshot_store=s))
    if profile.disable_onedrive_tasks:
        actions.append(OneDriveTasksAction(snapshot_store=s))
    if profile.disable_memory_diagnostic_tasks:
        actions.append(MemoryDiagnosticTasksAction(snapshot_store=s))
    if profile.disable_mcafee_tasks:
        actions.append(McAfeeTasksAction(snapshot_store=s))

    # ── System ────────────────────────────────────────────────────────────
    if profile.disable_system_restore:
        actions.append(SystemRestoreAction(snapshot_store=s))
    if profile.disable_fast_startup:
        actions.append(FastStartupAction(snapshot_store=s))
    if profile.disable_notifications:
        actions.append(NotificationAction(snapshot_store=s))
    if profile.disable_cortana:
        actions.append(CortanaAction(snapshot_store=s))
    if profile.disable_background_apps:
        actions.append(BackgroundAppsAction(snapshot_store=s))
    if profile.manage_pagefile:
        actions.append(PagefileAction(
            drive=profile.pagefile_drive,
            min_mb=profile.pagefile_min_mb,
            max_mb=profile.pagefile_max_mb,
            snapshot_store=s,
        ))

    return actions


class OsConfigController:
    """
    Apply and revert a set of OS configuration actions defined by a profile.

    Args:
        profile:        :class:`OsConfigProfile` declaring which actions to run.
        build_info:     :class:`WindowsBuildInfo` for the current machine.
                        If ``None``, will be auto-detected via
                        :func:`get_build_info`.
        state_manager:  Optional :class:`OsConfigStateManager` for snapshot
                        persistence across reboots.
    """

    def __init__(
        self,
        profile: Optional[OsConfigProfile] = None,
        build_info: Optional[WindowsBuildInfo] = None,
        state_manager: Optional[OsConfigStateManager] = None,
    ) -> None:
        self._profile = profile or OsConfigProfile()
        self._build_info = build_info or get_build_info()
        self._state_manager = state_manager
        self._snapshot: Dict[str, Any] = {}
        self._actions: List[AbstractOsAction] = _build_action_list(
            self._profile, self._snapshot
        )

    # ─────────────────────────────────────────────────────────────────────
    # Public helpers
    # ─────────────────────────────────────────────────────────────────────

    @property
    def profile(self) -> OsConfigProfile:
        """The profile this controller was constructed with."""
        return self._profile

    @property
    def actions(self) -> List[AbstractOsAction]:
        """Ordered list of action instances (read-only copy)."""
        return list(self._actions)

    @property
    def snapshot(self) -> Dict[str, Any]:
        """Shared snapshot store (populated after :meth:`apply_all`)."""
        return self._snapshot

    # ─────────────────────────────────────────────────────────────────────
    # Core operations
    # ─────────────────────────────────────────────────────────────────────

    def apply_all(self) -> Dict[str, str]:
        """
        Apply every enabled action in profile order.

        Unsupported actions are skipped (warn) or raise
        :class:`OsConfigNotSupportedError` when
        ``profile.fail_on_unsupported`` is ``True``.

        After all actions have been applied the snapshot is persisted via
        the state manager (if one was provided).

        Returns:
            Dict mapping action name → ``"applied"``, ``"skipped"``,
            ``"unsupported"``, or ``"error:<message>"``.
        """
        results: Dict[str, str] = {}

        for action in self._actions:
            name = action.name
            if not action.supported_on(self._build_info):
                if self._profile.fail_on_unsupported:
                    raise OsConfigNotSupportedError(
                        f"{name} is not supported on this build "
                        f"(build={self._build_info.build}, "
                        f"edition={self._build_info.edition})"
                    )
                logger.warning(f"[OsConfigController] Skipping {name} – not supported")
                results[name] = "unsupported"
                continue

            try:
                action.apply()
                results[name] = "applied"
            except OsConfigActionError as exc:
                logger.error(f"[OsConfigController] {name}.apply() failed: {exc}")
                results[name] = f"error:{exc}"

        # Persist snapshot after all actions applied
        if self._state_manager is not None:
            try:
                self._state_manager.save(self._snapshot)
            except Exception as exc:   # pragma: no cover
                logger.warning(
                    f"[OsConfigController] Failed to persist snapshot: {exc}"
                )

        return results

    def revert_all(self) -> Dict[str, str]:
        """
        Revert every action in **reverse** order.

        If a state manager is present and the snapshot file exists, the
        snapshot is loaded from disk first (enabling post-reboot revert).

        Returns:
            Dict mapping action name → ``"reverted"``, ``"unsupported"``,
            or ``"error:<message>"``.
        """
        # Restore snapshot from disk if available
        if self._state_manager is not None and self._state_manager.exists():
            try:
                loaded = self._state_manager.load()
                self._snapshot.update(loaded)
                logger.debug("[OsConfigController] Snapshot restored from disk")
            except Exception as exc:   # pragma: no cover
                logger.warning(
                    f"[OsConfigController] Could not load snapshot: {exc}"
                )

        results: Dict[str, str] = {}

        for action in reversed(self._actions):
            name = action.name
            if not action.supported_on(self._build_info):
                results[name] = "unsupported"
                continue

            try:
                action.revert()
                results[name] = "reverted"
            except OsConfigActionError as exc:
                logger.error(f"[OsConfigController] {name}.revert() failed: {exc}")
                results[name] = f"error:{exc}"

        # Clean up snapshot file after successful revert
        if self._state_manager is not None:
            try:
                self._state_manager.delete()
            except Exception as exc:   # pragma: no cover
                logger.warning(
                    f"[OsConfigController] Failed to delete snapshot file: {exc}"
                )

        return results

    def check_all(self) -> Dict[str, Optional[bool]]:
        """
        Query the current state of every action without making changes.

        Unsupported actions map to ``None``; supported actions map to
        the ``bool`` returned by :meth:`~AbstractOsAction.check`.

        Returns:
            Dict mapping action name → bool or None.
        """
        results: Dict[str, Optional[bool]] = {}
        for action in self._actions:
            if not action.supported_on(self._build_info):
                results[action.name] = None
            else:
                try:
                    results[action.name] = action.check()
                except Exception as exc:
                    logger.warning(
                        f"[OsConfigController] {action.name}.check() raised: {exc}"
                    )
                    results[action.name] = None
        return results
