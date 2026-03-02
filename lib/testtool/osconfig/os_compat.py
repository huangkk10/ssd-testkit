"""
OsConfig OS Compatibility Layer

Provides Windows build/edition detection and a Capability Matrix that
maps each configurable feature to the minimum OS build and excluded
editions where it is applicable.

Usage::

    from lib.testtool.osconfig.os_compat import get_build_info, is_supported

    build = get_build_info()
    print(build.version_tag)          # "win10" or "win11"
    print(build.build)                 # e.g. 19045
    print(build.edition)               # "Pro" / "Home" / "Enterprise" / "Server"

    if is_supported("onedrive_metered", build):
        # safe to apply
        ...
"""

import platform
import winreg
import sys
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List

# Ensure project root on path so lib.logger is importable
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.logger import get_module_logger

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WindowsBuildInfo:
    """
    Snapshot of the current Windows version information.

    Attributes:
        major:       Windows major version number (always 10 for Win10/11).
        build:       Windows build number (e.g. 19045 for 22H2, 22621 for Win11 22H2).
        edition:     Edition string extracted from ProductName registry value.
                     Examples: ``"Home"``, ``"Pro"``, ``"Enterprise"``, ``"Server"``.
        version_tag: Human-readable tag – ``"win10"`` or ``"win11"``.
        product_name: Full product name string from registry
                      (e.g. ``"Windows 10 Pro"``).
    """
    major: int
    build: int
    edition: str
    version_tag: str
    product_name: str = field(default="")


# Capability Matrix
# Each key is a feature identifier used by Action classes.
# ``min_build``        – inclusive lower bound on Windows build number.
# ``exclude_editions`` – list of edition substrings to exclude (case-insensitive).
#                        e.g. ``["Server"]`` skips the feature on Server editions.
CAPABILITIES: Dict[str, Dict[str, Any]] = {
    # ── Services ─────────────────────────────────────────────────
    "search_index": {
        "min_build": 0,
        "exclude_editions": ["Server"],  # WSearch may not exist on Server Core
        "description": "Disable Windows Search Index (WSearch service)",
    },
    "sysmain": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable SysMain / Superfetch service",
    },
    "windows_update": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Windows Update (wuauserv)",
    },
    "wer": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Windows Error Reporting (WerSvc)",
    },
    "telemetry": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Telemetry / DiagTrack service",
    },
    "pcasvc": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Program Compatibility Assistant (PcaSvc)",
    },
    # ── OneDrive ─────────────────────────────────────────────────
    "onedrive_metered": {
        "min_build": 14393,             # RS1 (Anniversary Update, 1607)
        "exclude_editions": [],
        "description": "Disable OneDrive sync over metered connections",
    },
    "onedrive_filesync": {
        "min_build": 14393,             # RS1
        "exclude_editions": [],
        "description": "Prevent OneDrive file storage (DisableFileSyncNGSC)",
    },
    # ── Security ─────────────────────────────────────────────────
    "defender_realtime": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Defender Real-time Monitoring",
    },
    "defender_tamper_protection_api": {
        "min_build": 18362,             # 1903 – Tamper Protection introduced
        "exclude_editions": [],
        "description": "Disable Defender via PowerShell Set-MpPreference (1903+)",
    },
    "memory_integrity": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Core Isolation / Memory Integrity",
    },
    "vuln_driver_blocklist": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Vulnerable Driver Blocklist",
    },
    "firewall": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Windows Firewall (all profiles)",
    },
    "uac": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable UAC (EnableLUA)",
    },
    # ── Boot ─────────────────────────────────────────────────────
    "test_signing": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Enable Test Signing Mode (bcdedit)",
    },
    "recovery": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Recovery Mode (bcdedit)",
    },
    "auto_reboot": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Auto Reboot on BSOD",
    },
    "auto_admin_logon": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Enable Auto Admin Logon",
    },
    "memory_dump": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Enable Small Memory Dump",
    },
    # ── Power ────────────────────────────────────────────────────
    "power_plan": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Set Power Plan",
    },
    "monitor_timeout": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Monitor timeout (AC + DC)",
    },
    "standby_timeout": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Standby timeout (AC + DC)",
    },
    "hibernate_timeout": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Hibernate timeout (AC + DC)",
    },
    "disk_timeout": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Disk timeout (AC + DC)",
    },
    "unattended_sleep": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Unattended Sleep",
    },
    "hibernation_file": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Hibernation file (powercfg /h off)",
    },
    # ── Schedule ─────────────────────────────────────────────────
    "defrag_schedule": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Scheduled Defrag",
    },
    "defender_scan_schedule": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Windows Defender Scheduled Scan",
    },
    # ── System ───────────────────────────────────────────────────
    "system_restore": {
        "min_build": 0,
        "exclude_editions": ["Server"],
        "description": "Disable System Restore",
    },
    "fast_startup": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Fast Startup",
    },
    "notifications": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Windows Notifications / Action Center",
    },
    "cortana": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Cortana",
    },
    "background_apps": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Disable Background Apps",
    },
    "pagefile": {
        "min_build": 0,
        "exclude_editions": [],
        "description": "Configure Virtual Memory / Pagefile",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_registry_str(key_path: str, value_name: str) -> str:
    """Read a REG_SZ / REG_EXPAND_SZ value from HKEY_LOCAL_MACHINE."""
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
        value, _ = winreg.QueryValueEx(key, value_name)
        return str(value)


def _detect_edition(product_name: str) -> str:
    """
    Extract a normalised edition string from a full product name.

    Returns one of: ``"Home"``, ``"Pro"``, ``"Enterprise"``,
    ``"Education"``, ``"Server"``, ``"Unknown"``.
    """
    name_lower = product_name.lower()
    if "server" in name_lower:
        return "Server"
    if "enterprise" in name_lower:
        return "Enterprise"
    if "education" in name_lower:
        return "Education"
    if "home" in name_lower:
        return "Home"
    if "pro" in name_lower:
        return "Pro"
    return "Unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_build_info() -> WindowsBuildInfo:
    """
    Detect the current Windows version and return a :class:`WindowsBuildInfo`.

    Reads from ``HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion``
    (same approach as ``Common.get_detailed_windows_version()``).

    Returns:
        :class:`WindowsBuildInfo` populated with live system data.

    Raises:
        OSError: If the registry key cannot be opened (non-Windows environment).
    """
    reg_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    try:
        product_name = _read_registry_str(reg_path, "ProductName")
        current_build_str = _read_registry_str(reg_path, "CurrentBuild")
    except OSError as exc:
        logger.warning(f"os_compat: cannot read Windows version from registry: {exc}")
        # Return a neutral sentinel so downstream code can still run in CI
        return WindowsBuildInfo(
            major=0, build=0, edition="Unknown", version_tag="unknown",
            product_name="Unknown",
        )

    build = int(current_build_str)
    major = 10  # both Win10 and Win11 report major=10

    # Win11 started at build 22000
    version_tag = "win11" if build >= 22000 else "win10"

    # Normalise product name: Win11 may still read "Windows 10 *"
    if "Windows 10" in product_name and build >= 22000:
        product_name = product_name.replace("Windows 10", "Windows 11")

    edition = _detect_edition(product_name)

    logger.info(
        f"os_compat: detected {product_name} (build {build}, "
        f"edition={edition}, tag={version_tag})"
    )
    return WindowsBuildInfo(
        major=major,
        build=build,
        edition=edition,
        version_tag=version_tag,
        product_name=product_name,
    )


def is_supported(feature: str, build_info: WindowsBuildInfo) -> bool:
    """
    Check whether *feature* is supported on the given OS build.

    Args:
        feature:    A key from :data:`CAPABILITIES`.
        build_info: The result of :func:`get_build_info`.

    Returns:
        ``True`` if the feature can be applied; ``False`` otherwise.

    Raises:
        KeyError: If *feature* is not a known capability key.

    Example::

        build = get_build_info()
        if is_supported("onedrive_metered", build):
            OneDriveAction().apply()
    """
    if feature not in CAPABILITIES:
        raise KeyError(f"Unknown capability: '{feature}'. "
                       f"Known keys: {sorted(CAPABILITIES)}")

    cap = CAPABILITIES[feature]

    # Build number check
    if build_info.build < cap["min_build"]:
        logger.debug(
            f"os_compat: '{feature}' not supported – "
            f"build {build_info.build} < required {cap['min_build']}"
        )
        return False

    # Edition exclusion check
    for excluded in cap["exclude_editions"]:
        if excluded.lower() in build_info.edition.lower():
            logger.debug(
                f"os_compat: '{feature}' not supported – "
                f"edition '{build_info.edition}' is excluded"
            )
            return False

    return True


def get_capability_description(feature: str) -> str:
    """Return the human-readable description for a capability key."""
    if feature not in CAPABILITIES:
        raise KeyError(f"Unknown capability: '{feature}'")
    return CAPABILITIES[feature]["description"]


def list_unsupported_features(build_info: WindowsBuildInfo) -> List[str]:
    """
    Return a list of all feature keys that are NOT supported on *build_info*.

    Useful for pre-flight logging before applying a profile.
    """
    return [f for f in CAPABILITIES if not is_supported(f, build_info)]
