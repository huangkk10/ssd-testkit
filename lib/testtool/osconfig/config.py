"""
OsConfig — OsConfigProfile

Dataclass that declares which OS settings the controller should manage.
Each boolean field corresponds to exactly one action class; setting it to
``True`` means "apply this action".

Special case: ``power_plan`` is a string (plan name) instead of a bool;
a non-empty string activates :class:`PowerPlanAction`.

``pagefile_*`` fields are companion parameters for :class:`PagefileAction`.

Usage::

    from lib.testtool.osconfig.config import OsConfigProfile

    # Enable every action (suitable for a clean lab machine)
    profile = OsConfigProfile.default()

    # Select subset
    profile = OsConfigProfile(
        disable_search_index=True,
        disable_windows_update=True,
        power_plan="high_performance",
        disable_monitor_timeout=True,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OsConfigProfile:
    """
    Declares which OS-level actions the :class:`OsConfigController` should
    apply/revert.

    All boolean fields default to ``False`` (disabled / do-nothing).
    Use :meth:`default` to obtain a profile with **all** actions enabled.

    Args:
        # ── Services ──────────────────────────────────────────────────────
        disable_search_index:       Disable Windows Search (WSearch) service.
        disable_sysmain:            Disable SysMain (Superfetch) service.
        disable_windows_update:     Disable Windows Update service.
        disable_wer:                Disable Windows Error Reporting service.
        disable_telemetry:          Disable DiagTrack (telemetry) service.
        disable_pcasvc:             Disable Program Compatibility Assistant.

        # ── OneDrive + Security ────────────────────────────────────────────
        disable_onedrive:           Disable OneDrive via policy.
        disable_defender:           Disable Windows Defender real-time protection.
        disable_memory_integrity:   Disable HVCI memory integrity (VBS).
        disable_vuln_driver_blocklist: Disable vulnerable driver blocklist.
        disable_firewall:           Disable Windows Firewall on all profiles.
        disable_uac:                Disable UAC prompt (EnableLUA=0).

        # ── Boot ──────────────────────────────────────────────────────────
        enable_test_signing:        Enable bcdedit test-signing mode.
        disable_test_signing:       Disable bcdedit test-signing mode (ensure it is off).
        disable_recovery:           Disable WinRE automatic recovery.
        disable_auto_reboot:        Disable automatic reboot after BSOD.
        enable_auto_admin_logon:    Enable auto-logon (AutoAdminLogon=1).
        auto_login_username:        Username for auto-logon (sets DefaultUserName).
        auto_login_password:        Password for auto-logon (sets DefaultPassword; lab only).
        auto_login_domain:          Domain for auto-logon (sets DefaultDomainName).
        set_small_memory_dump:      Set crash dump to small/minidump type.

        # ── Power ──────────────────────────────────────────────────────────
        power_plan:                 Power plan name to activate.  One of
                                    ``"balanced"``, ``"high_performance"``,
                                    ``"power_saver"``, or ``""`` to skip.
        disable_monitor_timeout:    Set monitor-off timeout to 0 (never).
        disable_standby_timeout:    Set standby timeout to 0 (never).
        disable_hibernate_timeout:  Set hibernate timeout to 0 (never).
        disable_disk_timeout:       Set disk spindown timeout to 0 (never).
        disable_hibernation:        Run ``powercfg /hibernate off``.
        disable_unattended_sleep:   Set unattended-sleep timeout to 0.

        # ── Schedule ──────────────────────────────────────────────────────
        disable_defrag_schedule:    Disable scheduled disk defragmentation.
        disable_defender_scan_schedule: Disable Windows Defender scheduled scan.
        disable_edge_update_tasks:  Disable Microsoft Edge update scheduled tasks
                                    (MicrosoftEdgeUpdateTaskMachineCore,
                                    MicrosoftEdgeUpdateTaskMachineUA).
        disable_onedrive_tasks:     Disable OneDrive scheduled tasks
                                    (Reporting / Standalone Update / Startup,
                                    all SID variants discovered dynamically).
        disable_memory_diagnostic_tasks: Disable the MemoryDiagnostic\\RunFullMemoryDiagnostic
                                    scheduled task.
        disable_mcafee_tasks:       Disable McAfee scheduled tasks when McAfee is
                                    pre-installed (McAfee Auto Maintenance Task Agent,
                                    DAD.WPS.Execute.Updates).  No-op if McAfee is absent.

        # ── System ────────────────────────────────────────────────────────
        disable_system_restore:     Disable System Restore on C:\\.
        disable_fast_startup:       Disable fast startup (hiberboot).
        disable_notifications:      Disable Action Centre / notification toast.
        disable_cortana:            Disable Cortana via policy.
        disable_background_apps:    Block apps from running in background.
        manage_pagefile:            Configure fixed-size pagefile.
        pagefile_drive:             Drive letter for pagefile (default ``"C:"``).
        pagefile_min_mb:            Minimum pagefile size in MiB (default 4096).
        pagefile_max_mb:            Maximum pagefile size in MiB (default 8192).

        # ── Global ────────────────────────────────────────────────────────
        fail_on_unsupported:        Raise instead of warn when an action is not
                                    supported on the current OS build.
    """

    # ── Services ──────────────────────────────────────────────────────────
    disable_search_index: bool = False
    disable_sysmain: bool = False
    disable_windows_update: bool = False
    disable_wer: bool = False
    disable_telemetry: bool = False
    disable_pcasvc: bool = False

    # ── OneDrive + Security ────────────────────────────────────────────────
    disable_onedrive: bool = False
    disable_defender: bool = False
    disable_memory_integrity: bool = False
    disable_vuln_driver_blocklist: bool = False
    disable_firewall: bool = False
    disable_uac: bool = False

    # ── Boot ──────────────────────────────────────────────────────────────
    enable_test_signing: bool = False
    disable_test_signing: bool = False
    disable_recovery: bool = False
    disable_auto_reboot: bool = False
    enable_auto_admin_logon: bool = False
    auto_login_username: str = ""
    auto_login_password: str = ""
    auto_login_domain: str = ""
    set_small_memory_dump: bool = False

    # ── Power ──────────────────────────────────────────────────────────────
    power_plan: str = ""
    disable_monitor_timeout: bool = False
    disable_standby_timeout: bool = False
    disable_hibernate_timeout: bool = False
    disable_disk_timeout: bool = False
    disable_hibernation: bool = False
    disable_unattended_sleep: bool = False

    # ── Schedule ──────────────────────────────────────────────────────────
    disable_defrag_schedule: bool = False
    disable_defender_scan_schedule: bool = False
    disable_edge_update_tasks: bool = False
    disable_onedrive_tasks: bool = False
    disable_memory_diagnostic_tasks: bool = False
    disable_mcafee_tasks: bool = False

    # ── System ────────────────────────────────────────────────────────────
    disable_system_restore: bool = False
    disable_fast_startup: bool = False
    disable_notifications: bool = False
    disable_cortana: bool = False
    disable_background_apps: bool = False
    manage_pagefile: bool = False
    pagefile_drive: str = "C:"
    pagefile_min_mb: int = 4096
    pagefile_max_mb: int = 8192

    # ── Global ────────────────────────────────────────────────────────────
    fail_on_unsupported: bool = False

    # ──────────────────────────────────────────────────────────────────────

    @classmethod
    def default(cls) -> "OsConfigProfile":
        """
        Return a profile with **all** boolean actions enabled and sensible
        defaults for parameterised actions.

        Suitable for a freshly installed lab machine where every optimisation
        should be applied before running storage workloads.
        """
        return cls(
            # Services
            disable_search_index=True,
            disable_sysmain=True,
            disable_windows_update=True,
            disable_wer=True,
            disable_telemetry=True,
            disable_pcasvc=True,
            # Security / OneDrive
            disable_onedrive=True,
            disable_defender=True,
            disable_memory_integrity=True,
            disable_vuln_driver_blocklist=True,
            disable_firewall=True,
            disable_uac=True,
            # Boot
            enable_test_signing=True,
            disable_recovery=True,
            disable_auto_reboot=True,
            enable_auto_admin_logon=True,
            set_small_memory_dump=True,
            # Power
            power_plan="high_performance",
            disable_monitor_timeout=True,
            disable_standby_timeout=True,
            disable_hibernate_timeout=True,
            disable_disk_timeout=True,
            disable_hibernation=True,
            disable_unattended_sleep=True,
            # Schedule
            disable_defrag_schedule=True,
            disable_defender_scan_schedule=True,
            disable_edge_update_tasks=True,
            disable_onedrive_tasks=True,
            disable_memory_diagnostic_tasks=True,
            disable_mcafee_tasks=True,
            # System
            disable_system_restore=True,
            disable_fast_startup=True,
            disable_notifications=True,
            disable_cortana=True,
            disable_background_apps=True,
            manage_pagefile=True,
            pagefile_drive="C:",
            pagefile_min_mb=4096,
            pagefile_max_mb=8192,
        )

    def enabled_actions(self) -> list:
        """
        Return a list of ``(field_name, value)`` pairs for every action that
        is enabled (bool ``True`` or non-empty string ``power_plan``).

        Useful for introspection / logging without importing action classes.
        """
        result = []
        for fname, fvalue in self.__dict__.items():
            if fname in ("pagefile_drive", "pagefile_min_mb", "pagefile_max_mb",
                         "fail_on_unsupported",
                         "auto_login_username", "auto_login_password", "auto_login_domain"):
                continue
            if isinstance(fvalue, bool) and fvalue:
                result.append((fname, fvalue))
            elif fname == "power_plan" and fvalue:
                result.append((fname, fvalue))
        return result
