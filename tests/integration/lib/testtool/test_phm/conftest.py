"""
PHM Integration Test Fixtures and Configuration

Provides pytest fixtures for PHM integration tests.

Requirements
------------
- PHM installer present at configured path (or PHM already installed)
- Real Windows environment
- Run as Administrator

Environment-variable overrides
-------------------------------
PHM_INSTALLER_PATH    Full path to phm_nda_*.exe installer
PHM_INSTALL_DIR       PHM installation target directory
PHM_LOG_DIR           Output directory for this test session
PHM_TIMEOUT           Per-test timeout in seconds (default 600)
"""

import os
import time
import pytest
from pathlib import Path
from typing import Dict, Any


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real environment)"
    )
    config.addinivalue_line(
        "markers", "requires_phm: mark test as requiring PHM installation or installer"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


@pytest.fixture(scope="session")
def test_root() -> Path:
    """Return the workspace root (ssd-testkit/)."""
    return Path(__file__).resolve().parents[5]


@pytest.fixture(scope="session")
def phm_env(test_root) -> Dict[str, Any]:
    """
    Provide PHM test environment configuration.

    Precedence:
      1. Environment variable override
      2. tests/integration/bin/PHM/<installer>  (installer present in repo)
      3. Default install path for installed PHM

    Returns:
        Dictionary with test environment configuration.
    """
    bin_path = test_root / "tests" / "integration" / "bin" / "PHM"
    default_installer = str(bin_path / "phm_nda_V4.22.0_B25.02.06.02_H.exe")

    timestamp = int(time.time())
    testlog_dir = test_root / "tests" / "testlog"
    testlog_dir.mkdir(parents=True, exist_ok=True)
    default_log_dir = str(testlog_dir / f"phm_integration_{timestamp}")

    return {
        'installer_path': os.getenv("PHM_INSTALLER_PATH", default_installer),
        'install_path':   os.getenv(
            "PHM_INSTALL_DIR",
            r'C:\Program Files\Intel\Powerhouse Mountain'
        ),
        'log_dir':        os.getenv("PHM_LOG_DIR", default_log_dir),
        'timeout':        int(os.getenv("PHM_TIMEOUT", "600")),
        'executable_name': 'PHM.exe',
        'cycle_count':    1,
        'test_duration_minutes': 5,
        'enable_modern_standby': True,
    }


@pytest.fixture(scope="session")
def check_installer(phm_env):
    """Skip session if PHM installer is not present."""
    installer = Path(phm_env['installer_path'])
    if not installer.exists():
        pytest.skip(
            f"PHM installer not found at '{installer}'. "
            f"Set PHM_INSTALLER_PATH to the correct path, "
            f"or copy installer to tests/integration/bin/PHM/"
        )
    return phm_env


@pytest.fixture(scope="session")
def check_environment(phm_env):
    """Skip session if PHM is not installed (for tests that need a running PHM)."""
    from lib.testtool.phm.process_manager import PHMProcessManager
    pm = PHMProcessManager(
        install_path=phm_env['install_path'],
        executable_name=phm_env['executable_name'],
    )
    if not pm.is_installed():
        pytest.skip(
            f"PHM is not installed at '{phm_env['install_path']}'. "
            f"Run TestPHMInstallation tests first, or install PHM manually."
        )
    return phm_env


@pytest.fixture(scope="session")
def log_dir(phm_env) -> Path:
    """Create and return the session-scoped log directory."""
    path = Path(phm_env['log_dir'])
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def clean_log_dir(log_dir) -> Path:
    """
    Per-test sub-directory so output files do not bleed across tests.
    NOT deleted after the test — files remain for post-test inspection.
    """
    sub = log_dir / f"run_{int(time.time() * 1000)}"
    sub.mkdir(parents=True, exist_ok=True)
    return sub
