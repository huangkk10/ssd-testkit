"""
Windows ADK Configuration

Defines supported OS builds, directory paths per build, and default SPEC thresholds.
"""

import platform

# ---------------------------------------------------------------------------
# Supported Windows build numbers
# ---------------------------------------------------------------------------
SUPPORTED_BUILDS = {
    22000: "Windows 11 21H2",
    22621: "Windows 11 22H2/23H2",
    26100: "Windows 11 24H2",
    26200: "Windows 11 Insider Preview (build 26200)",
}

# ---------------------------------------------------------------------------
# Per-build: directory where WAC stores test results during assessment run
# (the "in-flight" directory polled while waiting for completion)
# ---------------------------------------------------------------------------
TEST_RESULT_DIRS = {
    22000: r"C:\Users\{user}\AppData\Local\Microsoft\Axe\Results\ ",
    22621: r"C:\Data\Test\Microsoft\Axe\Results\ ",
    26100: r"C:\Data\Test\Microsoft\Axe\Results\ ",
    26200: r"C:\Data\Test\Microsoft\Axe\Results\ ",
}

# ---------------------------------------------------------------------------
# WAC executable (same path for all supported builds)
# ---------------------------------------------------------------------------
WAC_EXE = (
    r"C:\Program Files (x86)\Windows Kits\10"
    r"\Assessment and Deployment Kit\Windows Assessment Toolkit\amd64\wac.exe"
)

# ---------------------------------------------------------------------------
# SPEC thresholds (default values — can be overridden via config dict)
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS = {
    # Boot Performance Fast Startup
    "FastStartup-Suspend-Overall-Time":   8,    # seconds (must be <)
    "FastStartup-Resume-Overall-Time":   12,    # seconds (must be <)
    "FastStartup-Resume-ReadHiberFile":  500,   # MB/s   (must be >)
    "FastStartup-Resume-BIOS":            5,    # seconds (must be <)
    # Standby Performance
    "Standby-Suspend-Overall-Time":       4,    # seconds (must be <)
    "Standby-Resume-Overall-Time":        3,    # seconds (must be <)
}

# ---------------------------------------------------------------------------
# Default controller configuration
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "log_path":         "./testlog",
    "log_prefix":       "",
    "check_result_spec": True,
    "scan_timeout_iterations": 20,
    "scan_interval_seconds":   70,
    "thresholds": DEFAULT_THRESHOLDS,
}


def merge_config(user_config: dict) -> dict:
    """Return a new config dict with user_config values overlaid on DEFAULT_CONFIG.

    Nested dicts (e.g. 'thresholds') are merged recursively so the caller only
    needs to specify the keys they want to override.
    """
    result = {}
    for key, default_val in DEFAULT_CONFIG.items():
        if key in user_config:
            if isinstance(default_val, dict) and isinstance(user_config[key], dict):
                result[key] = {**default_val, **user_config[key]}
            else:
                result[key] = user_config[key]
        else:
            result[key] = default_val
    return result


def get_build_number() -> int:
    """Return the Windows build number (third component of platform.version())."""
    return int(platform.version().split(".")[2])
