"""
Integration test fixtures for ChocoManager.

These fixtures provide real Chocolatey CLI access and ADK installer paths
for end-to-end testing of lib/testtool/choco_manager.py.
"""

import pytest
from pathlib import Path


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real environment)"
    )
    config.addinivalue_line(
        "markers", "requires_choco: mark test as requiring Chocolatey CLI on PATH"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow-running (ADK install/uninstall)"
    )


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the ssd-testkit repository root."""
    # tests/integration/lib/testtool/test_choco_manager/ → 5 parents up
    return Path(__file__).resolve().parents[5]


@pytest.fixture(scope="session")
def choco_manager(project_root):
    """Session-scoped ChocoManager instance pointing at the project root."""
    from lib.testtool.choco_manager import ChocoManager
    return ChocoManager(project_root=str(project_root))


@pytest.fixture(scope="session")
def adk_installer_path(project_root) -> Path:
    """
    Path to adksetup.exe used by the windows-adk nupkg install script.

    If the file is not present the requesting test is automatically skipped,
    because without the installer the choco install command cannot succeed.
    """
    path = project_root / "bin" / "installers" / "WindowsADK" / "22621" / "adksetup.exe"
    if not path.exists():
        pytest.skip(f"ADK installer not found at {path} – skipping install/uninstall tests")
    return path
