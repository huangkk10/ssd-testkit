"""
Integration Test Fixtures and Configuration — Windows ADK

Provides pytest fixtures and configuration for Windows ADK install /
uninstall integration tests.
"""

import os
import subprocess
import sys
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


def _find_choco() -> str | None:
    """Return the choco executable path, or None if not found."""
    candidates = [
        r"C:\ProgramData\chocolatey\bin\choco.exe",
        r"C:\ProgramData\chocolatey\choco.exe",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    try:
        subprocess.run(["choco", "--version"], capture_output=True, timeout=10, check=True)
        return "choco"
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return None


def _install_choco(test_root: Path) -> None:
    """
    Install Chocolatey offline using the bundled install_choco.ps1 script.
    Raises RuntimeError if the installation fails.
    """
    install_script = test_root / "bin" / "chocolatey" / "scripts" / "install_choco.ps1"
    if not install_script.is_file():
        raise RuntimeError(f"install_choco.ps1 not found: {install_script}")

    print(f"\n[check_environment] Chocolatey not found — installing via {install_script} ...")
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(install_script)],
        capture_output=False,   # stream output so progress is visible
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"install_choco.ps1 exited with code {result.returncode}. "
            "Check the output above for details."
        )
    print("[check_environment] Chocolatey installed successfully.")


@pytest.fixture(scope="session")
def check_environment(test_root, adk_env):
    """
    Session-scoped guard: ensure Chocolatey is available before any test runs.

    If Chocolatey is not found, installs it automatically using the bundled
    offline installer at bin/chocolatey/scripts/install_choco.ps1.
    Raises pytest.fail() if the auto-install also fails.
    """
    if _find_choco() is None:
        try:
            _install_choco(test_root)
        except RuntimeError as exc:
            pytest.fail(str(exc))

        # Confirm choco is now reachable after install
        if _find_choco() is None:
            pytest.fail(
                "Chocolatey installation appeared to succeed but choco.exe is still not found. "
                "You may need to restart the shell to refresh PATH."
            )
