"""
CDI Integration Test Fixtures and Configuration

Provides pytest fixtures for CDI (CrystalDiskInfo) integration tests.
These tests require:
  - DiskInfo64.exe present at the configured path
  - A real Windows environment with at least one physical disk
  - pywinauto installed
  - A display (or virtual desktop) for GUI interaction
"""

import os
import time
import shutil
import pytest
from pathlib import Path
from typing import Any, Dict


def pytest_configure(config):
    """Register custom markers for CDI integration tests."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real environment)"
    )
    config.addinivalue_line(
        "markers", "requires_cdi: mark test as requiring DiskInfo64.exe and a real disk"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_root() -> Path:
    """Return the tests/ directory (ssd-testkit/tests/), matching the burnin integration test convention."""
    return Path(__file__).resolve().parents[4]


@pytest.fixture(scope="session")
def cdi_env(test_root) -> Dict[str, Any]:
    """
    Provide CDI test environment configuration.

    All values can be overridden via environment variables:

    +---------------------------+-------------------------------------------+
    | Env var                   | Default                                   |
    +---------------------------+-------------------------------------------+
    | CDI_EXE_PATH              | <repo>/bin/CrystalDiskInfo/DiskInfo64.exe |
    | CDI_LOG_DIR               | <repo>/testlog/CDI_integration            |
    | CDI_DRIVE_LETTER          | C:                                        |
    | CDI_TIMEOUT               | 120                                       |
    +---------------------------+-------------------------------------------+
    """
    # Default paths - use shared tool binaries from the unit test bin directory,
    # consistent with the burnin integration test convention.
    cdi_bin_path = test_root / "unit" / "lib" / "testtool" / "bin" / "CrystalDiskInfo"
    default_exe = str(cdi_bin_path / "DiskInfo64.exe")

    timestamp = int(time.time())
    testlog_dir = test_root / "testlog"
    testlog_dir.mkdir(parents=True, exist_ok=True)
    default_log_dir = str(testlog_dir / f"CDI_integration_{timestamp}")

    env: Dict[str, Any] = {
        'executable_path': os.getenv("CDI_EXE_PATH", default_exe),
        'log_dir':         os.getenv("CDI_LOG_DIR",  default_log_dir),
        'drive_letter':    os.getenv("CDI_DRIVE_LETTER", "C:"),
        'timeout':         int(os.getenv("CDI_TIMEOUT", "120")),
    }
    return env


@pytest.fixture(scope="session")
def check_environment(cdi_env):
    """
    Validate environment before any integration test runs.
    Skips the entire session if DiskInfo64.exe is not found.
    """
    exe = Path(cdi_env['executable_path'])
    if not exe.exists():
        pytest.skip(
            f"DiskInfo64.exe not found at '{exe}'.  "
            f"Set CDI_EXE_PATH to the correct location."
        )
    return cdi_env


@pytest.fixture(scope="session")
def log_dir(cdi_env) -> Path:
    """Create and return the log directory for this test session."""
    path = Path(cdi_env['log_dir'])
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_log_dir(log_dir) -> Path:
    """
    Start each test with a clean sub-directory so output files do not
    bleed across tests.

    Yields the unique sub-dir path; does NOT delete it after the test so
    that files are available for post-test inspection.
    """
    sub = log_dir / f"run_{int(time.time() * 1000)}"
    sub.mkdir(parents=True, exist_ok=True)
    yield sub
