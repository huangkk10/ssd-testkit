"""
Integration test conftest for OsConfig.

Provides:
  - ``require_admin`` autouse fixture: skips entire module if not elevated
  - ``build_info`` fixture: real WindowsBuildInfo from the current machine
  - helper ``svc_state(name)`` to query actual service start type
"""

import ctypes
import subprocess
import sys
import os
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lib.testtool.osconfig.os_compat import get_build_info


# ── Admin guard ───────────────────────────────────────────────────────────────

def _is_admin() -> bool:
    """Return True when the current process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def require_admin():
    """
    Session-scoped fixture that skips this entire test module if the current
    process is not running with administrator privileges.

    Run with: `pytest -m integration` from an elevated terminal.
    """
    if not _is_admin():
        pytest.skip(
            "Integration tests require administrator privileges. "
            "Re-run from an elevated (admin) terminal.",
            allow_module_level=True,
        )


# ── Build info ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def build_info():
    """Real WindowsBuildInfo detected from the current machine."""
    return get_build_info()


# ── Service helpers ───────────────────────────────────────────────────────────

def svc_start_type(svc_name: str) -> str:
    """
    Return the StartType of a Windows service as a lowercase string:
    ``"auto"``, ``"demand"``, ``"disabled"``, or ``"unknown"``.
    """
    try:
        result = subprocess.run(
            ["sc", "qc", svc_name],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "START_TYPE" in line:
                parts = line.split()
                if len(parts) >= 2:
                    code = parts[1]
                    return {
                        "2": "auto",
                        "3": "demand",
                        "4": "disabled",
                    }.get(code, "unknown")
    except Exception:
        pass
    return "unknown"
