"""
PwrTest Integration Test Fixtures and Configuration

Provides pytest fixtures for PwrTest integration tests.

Requirements
------------
- pwrtest.exe present at the configured path (inside SmiWinTools)
- Real Windows environment with ACPI S3 / S0ix sleep support
- Run as Administrator (pwrtest requires elevated privileges)

Environment-variable overrides
-------------------------------
PWRTEST_EXE_PATH       Full path to pwrtest.exe (overrides os_name+os_version)
PWRTEST_OS_NAME        OS directory name: win7 | win10 | win11  (default: win11)
PWRTEST_OS_VERSION     OS version sub-dir (default: 25H2)
PWRTEST_LOG_DIR        Base directory for output files

Execution parameters (cycle_count, delay_seconds, wake_after_seconds,
timeout_seconds) are passed directly to PwrTestController in each test.
"""

import os
import time
import pytest
from pathlib import Path
from typing import Dict, Any


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires real environment)",
    )
    config.addinivalue_line(
        "markers",
        "requires_pwrtest: mark test as requiring pwrtest.exe",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running (sleep + resume cycle)",
    )


@pytest.fixture(scope="session")
def test_root() -> Path:
    """Return the workspace root (ssd-testkit/)."""
    return Path(__file__).resolve().parents[5]


@pytest.fixture(scope="session")
def pwrtest_env(test_root) -> Dict[str, Any]:
    """
    Provide PwrTest environment configuration for the test session.

    Resolution order for exe path:
      1. PWRTEST_EXE_PATH environment variable
      2. Auto-composed from PWRTEST_OS_NAME + PWRTEST_OS_VERSION
         under tests/unit/lib/testtool/bin/SmiWinTools/bin/x64/pwrtest/
    """
    os_name    = os.getenv("PWRTEST_OS_NAME",    "win11")
    os_version = os.getenv("PWRTEST_OS_VERSION", "25H2")

    bin_root   = (
        test_root
        / "tests" / "unit" / "lib" / "testtool" / "bin"
        / "SmiWinTools" / "bin" / "x64" / "pwrtest"
    )
    default_exe = str(bin_root / os_name / os_version / "pwrtest.exe")

    timestamp   = int(time.time())
    testlog_dir = test_root / "tests" / "testlog"
    testlog_dir.mkdir(parents=True, exist_ok=True)
    default_log_dir = str(testlog_dir / f"pwrtest_integration_{timestamp}")

    return {
        'executable_path': os.getenv("PWRTEST_EXE_PATH", ""),
        'pwrtest_base_dir': str(bin_root),
        'os_name':          os_name,
        'os_version':       os_version,
        'log_dir':          os.getenv("PWRTEST_LOG_DIR", default_log_dir),
    }


@pytest.fixture(scope="session")
def check_environment(pwrtest_env):
    """
    Skip the entire session if pwrtest.exe is not present.
    Also resolves the effective exe path so individual tests don't repeat it.
    """
    from lib.testtool.pwrtest.config import PwrTestConfig

    # Build a config dict and resolve the executable path
    cfg = PwrTestConfig.get_default_config()
    cfg.update({
        'executable_path': pwrtest_env['executable_path'],
        'pwrtest_base_dir': pwrtest_env['pwrtest_base_dir'],
        'os_name': pwrtest_env['os_name'],
        'os_version': pwrtest_env['os_version'],
    })
    exe = PwrTestConfig.resolve_executable_path(cfg)

    if not exe.exists():
        pytest.skip(
            f"pwrtest.exe not found at '{exe}'. "
            f"Set PWRTEST_EXE_PATH or adjust PWRTEST_OS_NAME/PWRTEST_OS_VERSION."
        )

    # Inject resolved exe path back so tests don't need to redo the logic
    pwrtest_env['_resolved_exe'] = str(exe)
    return pwrtest_env


@pytest.fixture(scope="session")
def log_dir(pwrtest_env) -> Path:
    """Create and return the session-scoped log directory."""
    path = Path(pwrtest_env['log_dir'])
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def clean_log_dir(log_dir) -> Path:
    """
    Per-test sub-directory so file outputs don't bleed across tests.
    NOT deleted after the test — files remain for post-run inspection.
    """
    sub = log_dir / f"run_{int(time.time() * 1000)}"
    sub.mkdir(parents=True, exist_ok=True)
    return sub
