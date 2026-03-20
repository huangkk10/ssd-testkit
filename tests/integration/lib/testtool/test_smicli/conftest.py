"""
Integration test fixtures for smicli Chocolatey packaging.
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
        "markers", "slow: mark test as slow-running (file copy / env var operations)"
    )


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the ssd-testkit repository root."""
    return Path(__file__).resolve().parents[5]


@pytest.fixture(scope="session")
def choco_manager(project_root):
    """Session-scoped ChocoManager."""
    from lib.testtool.choco_manager import ChocoManager
    return ChocoManager(project_root=str(project_root))


@pytest.fixture(scope="session")
def smicli_source(project_root) -> Path:
    """
    Path to the SmiCli source directory (bin/installers/SmiCli/v20251114A/).
    Auto-skips the test if the directory or SmiCli2.exe is not present.
    """
    path = project_root / "bin" / "installers" / "SmiCli" / "v20251114A"
    if not path.exists():
        pytest.skip(f"SmiCli source directory not found: {path}")
    if not (path / "SmiCli2.exe").exists():
        pytest.skip(f"SmiCli2.exe not found in {path}")
    return path
