"""
Integration Test Fixtures and Configuration — WinPVT

Provides pytest fixtures and configuration for WinPVT install /
uninstall integration tests.
"""

import os
import subprocess
import sys
import pytest
from pathlib import Path
from typing import Any, Dict


def pytest_configure(config):
    """Register custom markers for WinPVT integration tests."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real environment)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_winpvt: mark test as requiring WinPVT installer and Chocolatey"
    )


@pytest.fixture(scope="session")
def test_root() -> Path:
    """Repo root (5 levels up from this conftest.py)."""
    return Path(__file__).resolve().parents[5]


@pytest.fixture(scope="session")
def winpvt_env(test_root) -> Dict[str, Any]:
    """
    WinPVT test environment configuration.

    All values can be overridden via environment variables:
        WINPVT_CHOCO_ID      — Chocolatey package ID      (default: winpvt)
        WINPVT_VERSION       — Package version to install  (default: 11.16.0)
        WINPVT_INSTALL_DIR   — Expected install directory
    """
    install_dir = os.getenv(
        "WINPVT_INSTALL_DIR",
        r"C:\Program Files\Hewlett-Packard\WinPVT 11.16.0",
    )
    return {
        "choco_package_id": os.getenv("WINPVT_CHOCO_ID", "winpvt"),
        "version": os.getenv("WINPVT_VERSION", "11.16.0"),
        "install_dir": Path(install_dir),
        "binaries": ["WinPVT.exe"],
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
        capture_output=False,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"install_choco.ps1 exited with code {result.returncode}. "
            "Check the output above for details."
        )
    print("[check_environment] Chocolatey installed successfully.")


@pytest.fixture(scope="session")
def check_environment(test_root, winpvt_env):
    """
    Session-scoped guard: ensure Chocolatey and the WinPVT installer file are
    available before any test runs.

    If Chocolatey is not found, installs it automatically using the bundled
    offline installer at bin/chocolatey/scripts/install_choco.ps1.
    """
    # 1. Ensure Chocolatey is available
    if _find_choco() is None:
        try:
            _install_choco(test_root)
        except RuntimeError as exc:
            pytest.fail(str(exc))

        if _find_choco() is None:
            pytest.fail(
                "Chocolatey installation appeared to succeed but choco.exe is still not found. "
                "You may need to restart the shell to refresh PATH."
            )

    # 2. Ensure the WinPVT installer file is present
    version = winpvt_env["version"]
    installer_path = test_root / "bin" / "installers" / "winpvt" / version / "WinPVT.exe"
    if not installer_path.is_file():
        pytest.fail(
            f"WinPVT installer not found: {installer_path}\n"
            f"Run tool-manager/prepare_testcase.ps1 to download it first."
        )

    # 3. Ensure the nupkg exists
    nupkg_path = (
        test_root / "bin" / "chocolatey" / "packages" / "winpvt" / version
        / f"winpvt.{version}.nupkg"
    )
    if not nupkg_path.is_file():
        pytest.fail(
            f"WinPVT nupkg not found: {nupkg_path}\n"
            "Run: cd bin/chocolatey/packages/winpvt/<version> && choco pack winpvt.nuspec"
        )
