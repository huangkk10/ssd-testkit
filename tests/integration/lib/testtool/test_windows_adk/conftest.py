"""
Integration Test Fixtures and Configuration — Windows ADK

Provides pytest fixtures and configuration for Windows ADK install /
uninstall integration tests.
"""

import os
import subprocess
import pytest
from pathlib import Path
from typing import Any, Dict


def pytest_configure(config):
    """Register custom markers for Windows ADK integration tests."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real environment)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_windows_adk: mark test as requiring Windows ADK / Chocolatey"
    )


@pytest.fixture(scope="session")
def test_root() -> Path:
    """Repo root (5 levels up from this conftest.py)."""
    return Path(__file__).resolve().parents[5]


@pytest.fixture(scope="session")
def adk_env(test_root) -> Dict[str, Any]:
    """
    Windows ADK test environment configuration.

    All values can be overridden via environment variables:
        ADK_CHOCO_ID      — Chocolatey package ID      (default: windows-adk)
        ADK_VERSION       — Package version to install  (default: latest default)
        ADK_INSTALL_DIR   — Expected install directory
    """
    install_dir = os.getenv(
        "ADK_INSTALL_DIR",
        r"C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit",
    )
    return {
        "choco_package_id": os.getenv("ADK_CHOCO_ID", "windows-adk"),
        "version": os.getenv("ADK_VERSION") or None,  # None → use default from package_meta
        "install_dir": Path(install_dir),
        "binaries": ["wpr.exe", "wpa.exe", "xbootmgr.exe"],
    }


@pytest.fixture(scope="session")
def check_environment(adk_env):
    """
    Session-scoped guard: skip the suite when Chocolatey is unavailable.

    Does NOT require Windows ADK to be pre-installed; installation is part
    of the tests themselves.
    """
    choco_candidates = [
        r"C:\ProgramData\chocolatey\bin\choco.exe",
        r"C:\ProgramData\chocolatey\choco.exe",
    ]
    choco_found = any(Path(c).is_file() for c in choco_candidates)
    if not choco_found:
        try:
            subprocess.run(
                ["choco", "--version"],
                capture_output=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip(
                "Chocolatey (choco) not found — skipping Windows ADK integration tests"
            )
