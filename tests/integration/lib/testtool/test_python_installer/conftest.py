"""
PythonInstaller Integration Test Fixtures and Configuration

Provides pytest fixtures for PythonInstaller integration tests.

Requirements
------------
- Real Windows environment
- Administrator privileges (Python installer requires elevated rights)
- Internet access to python.org  OR  a pre-downloaded installer via env var

Environment-variable overrides
-------------------------------
PYTHON_INSTALLER_VERSION    Target Python version (default: 3.11)
PYTHON_INSTALLER_ARCH       Architecture: amd64 | win32 (default: amd64)
PYTHON_INSTALLER_PATH       Path to a pre-downloaded .exe (skips download)
PYTHON_INSTALLER_INSTALL_DIR  Where to install (default: testlog/py_install_test)
PYTHON_INSTALLER_TIMEOUT    Per-operation timeout in seconds (default: 300)

Run integration tests
---------------------
    pytest tests/integration/lib/testtool/test_python_installer/ -v -m "integration"

Skip integration tests
----------------------
    pytest ... -m "not integration"
"""

import os
import ctypes
import time
import urllib.request
import pytest
from pathlib import Path
from typing import Any, Dict


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires real Windows environment)",
    )
    config.addinivalue_line(
        "markers",
        "requires_python_installer: mark test as requiring Python installer accessibility",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running (install/uninstall takes minutes)",
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _is_admin() -> bool:
    """Return True if the current process has administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _can_reach_python_org(timeout: int = 10) -> bool:
    """Return True if python.org download server is reachable."""
    url = "https://www.python.org/ftp/python/"
    try:
        req = urllib.request.Request(url, method='HEAD')
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_root() -> Path:
    """Return the tests/ directory (ssd-testkit/tests/)."""
    return Path(__file__).resolve().parents[4]


@pytest.fixture(scope="session")
def python_installer_env(test_root) -> Dict[str, Any]:
    """
    Provide PythonInstaller test environment configuration.

    Installer search order (when PYTHON_INSTALLER_PATH is not set):
      1. tests/unit/lib/testtool/bin/python_installer/python-<ver>-<arch>.exe
         (pre-downloaded via tools/download_python_installer.py)
      2. Empty string → auto-download from python.org at test time

    +--------------------------------+------------------------------------------+
    | Env var                        | Default                                  |
    +--------------------------------+------------------------------------------+
    | PYTHON_INSTALLER_VERSION       | 3.11                                     |
    | PYTHON_INSTALLER_ARCH          | amd64                                    |
    | PYTHON_INSTALLER_PATH          | (auto-detect from bin dir, then download)|
    | PYTHON_INSTALLER_INSTALL_DIR   | <tests>/testlog/py_install_<ts>          |
    | PYTHON_INSTALLER_TIMEOUT       | 300                                      |
    +--------------------------------+------------------------------------------+
    """
    timestamp = int(time.time())
    version   = os.getenv("PYTHON_INSTALLER_VERSION", "3.11")
    arch      = os.getenv("PYTHON_INSTALLER_ARCH", "amd64")

    testlog_dir = test_root / "testlog"
    testlog_dir.mkdir(parents=True, exist_ok=True)

    default_install_dir  = str(testlog_dir / f"py_install_{timestamp}")
    default_download_dir = str(testlog_dir / "python_installer_cache")

    # --- Locate pre-downloaded installer in the bin directory ---
    # Accepts both 2-part ('3.11') and 3-part ('3.11.0') version strings.
    bin_dir = (
        test_root / "unit" / "lib" / "testtool" / "bin" / "python_installer"
    )
    # Try exact match first, then glob for any patch version
    ver_parts = version.split('.')
    major_minor = f"{ver_parts[0]}.{ver_parts[1]}"
    candidates = sorted(bin_dir.glob(f"python-{major_minor}*-{arch}.exe"))
    default_installer = str(candidates[-1]) if candidates else ""

    return {
        'version':        version,
        'architecture':   arch,
        'installer_path': os.getenv("PYTHON_INSTALLER_PATH", default_installer),
        'install_dir':    os.getenv("PYTHON_INSTALLER_INSTALL_DIR", default_install_dir),
        'download_dir':   default_download_dir,
        'timeout':        int(os.getenv("PYTHON_INSTALLER_TIMEOUT", "300")),
        # Never add to system PATH during tests to avoid polluting the environment
        'add_to_path':    False,
    }


@pytest.fixture(scope="session")
def check_environment(python_installer_env):
    """
    Guard fixture: skip the session when the environment is not suitable.

    Checks (in order):
      1. Running on Windows
      2. Administrator privileges (installer requires elevation)
      3. A pre-downloaded installer exists  OR  python.org is reachable
    """
    import platform
    if platform.system() != 'Windows':
        pytest.skip("PythonInstaller integration tests require Windows.")

    if not _is_admin():
        pytest.skip(
            "PythonInstaller integration tests must be run as Administrator "
            "(Python installer requires elevated privileges)."
        )

    installer_path = python_installer_env['installer_path']
    if installer_path:
        if not Path(installer_path).is_file():
            pytest.skip(
                f"Pre-downloaded installer not found: '{installer_path}'. "
                "Run:  python tools/download_python_installer.py  to fetch it, "
                "or set PYTHON_INSTALLER_PATH to a valid .exe path."
            )
    else:
        # No pre-downloaded installer — need internet access for auto-download
        if not _can_reach_python_org():
            pytest.skip(
                "No pre-downloaded installer found and python.org is not reachable. "
                "Pre-download the installer with:\n"
                "  python tools/download_python_installer.py\n"
                "Then re-run the tests (the installer will be auto-detected)."
            )

    return python_installer_env


@pytest.fixture(scope="session")
def log_dir(python_installer_env) -> Path:
    """Session-scoped log / output directory."""
    path = Path(python_installer_env['install_dir']).parent / "python_installer_integration"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def clean_log_dir(log_dir) -> Path:
    """Per-test sub-directory.  Files are kept after the test for inspection."""
    sub = log_dir / f"run_{int(time.time() * 1000)}"
    sub.mkdir(parents=True, exist_ok=True)
    yield sub


@pytest.fixture
def isolated_install_dir(tmp_path) -> Path:
    """
    Per-test isolated install directory under tmp_path.
    Automatically removed by pytest after the test completes.
    """
    install_dir = tmp_path / "Python_integration_test"
    install_dir.mkdir(parents=True, exist_ok=True)
    return install_dir
