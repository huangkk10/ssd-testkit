# lib/testtool/osconfig/actions/__init__.py
"""
OsConfig Actions sub-package.

Each module in this package implements one OS configuration action via a
concrete subclass of :class:`~lib.testtool.osconfig.actions.base_action.AbstractOsAction`.
"""

from .base_action import AbstractOsAction
from ._base_service_action import BaseServiceAction

# ── Phase 2: Service Actions ──────────────────────────────────────────────
from .search_index import SearchIndexAction
from .sysmain import SysMainAction
from .windows_update import WindowsUpdateAction
from .wer import WerAction
from .telemetry import TelemetryAction
from .pcasvc import PcaSvcAction

# ── Phase 3: OneDrive + Security Actions ─────────────────────────────────
from .onedrive import OneDriveAction
from .defender import DefenderAction
from .memory_integrity import MemoryIntegrityAction
from .vuln_driver_blocklist import VulnDriverBlocklistAction
from .firewall import FirewallAction
from .uac import UacAction

# ── Phase 4: Boot Actions ─────────────────────────────────────────────────
from .test_signing import TestSigningAction, DisableTestSigningAction
from .recovery import RecoveryAction
from .auto_reboot import AutoRebootAction
from .auto_admin_logon import AutoAdminLogonAction
from .memory_dump import MemoryDumpAction

# ── Phase 4: Power Actions ────────────────────────────────────────────────
from .power_plan import PowerPlanAction
from .power_timeout import PowerTimeoutAction
from .hibernation import HibernationAction, UnattendedSleepAction

# ── Phase 4: Schedule Actions ─────────────────────────────────────────────
from .defrag_schedule import DefragScheduleAction
from .defender_scan_schedule import DefenderScanScheduleAction
from .edge_update_tasks import EdgeUpdateTasksAction
from .onedrive_tasks import OneDriveTasksAction
from .memory_diagnostic_tasks import MemoryDiagnosticTasksAction
from .mcafee_tasks import McAfeeTasksAction
# ── Phase 4: System Actions ───────────────────────────────────────────────
from .system_restore import SystemRestoreAction
from .fast_startup import FastStartupAction
from .notifications import NotificationAction
from .cortana import CortanaAction
from .background_apps import BackgroundAppsAction
from .pagefile import PagefileAction

__all__ = [
    # Base classes
    "AbstractOsAction",
    "BaseServiceAction",
    # Phase 2 – Services
    "SearchIndexAction",
    "SysMainAction",
    "WindowsUpdateAction",
    "WerAction",
    "TelemetryAction",
    "PcaSvcAction",
    # Phase 3 – OneDrive + Security
    "OneDriveAction",
    "DefenderAction",
    "MemoryIntegrityAction",
    "VulnDriverBlocklistAction",
    "FirewallAction",
    "UacAction",
    # Phase 4 – Boot
    "TestSigningAction",
    "DisableTestSigningAction",
    "RecoveryAction",
    "AutoRebootAction",
    "AutoAdminLogonAction",
    "MemoryDumpAction",
    # Phase 4 – Power
    "PowerPlanAction",
    "PowerTimeoutAction",
    "HibernationAction",
    "UnattendedSleepAction",
    # Phase 4 – Schedule
    "DefragScheduleAction",
    "DefenderScanScheduleAction",
    "EdgeUpdateTasksAction",
    "OneDriveTasksAction",
    "MemoryDiagnosticTasksAction",
    "McAfeeTasksAction",
    # Phase 4 – System
    "SystemRestoreAction",
    "FastStartupAction",
    "NotificationAction",
    "CortanaAction",
    "BackgroundAppsAction",
    "PagefileAction",
]
