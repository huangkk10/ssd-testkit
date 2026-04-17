"""
WinPVT Install / Uninstall Integration Tests

Verifies that WinPVT can be installed and uninstalled through
ChocoManager, and that the expected binaries are present after
installation and absent after uninstallation.

Requirements:
    - Windows OS with Administrator privileges
    - Chocolatey must be installed (or will be auto-installed via install_choco.ps1)
    - WinPVT installer (WinPVT.exe) must exist under
      bin/installers/winpvt/11.16.0/WinPVT.exe
    - The offline nupkg must exist under
      bin/chocolatey/packages/winpvt/11.16.0/winpvt.11.16.0.nupkg

Run:
    pytest tests/integration/lib/testtool/test_winpvt/ -v -s
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.testtool.choco_manager import ChocoManager


@pytest.mark.integration
@pytest.mark.requires_winpvt
@pytest.mark.slow
class TestWinPVTInstallation:
    """Tests for WinPVT installation and uninstallation via Chocolatey."""

    def test_install(self, winpvt_env, check_environment):
        """
        Install WinPVT and verify the expected binary is present.

        Steps:
            1. Uninstall if already installed (idempotent setup).
            2. Run ChocoManager.install().
            3. Assert the result is successful.
            4. Assert WinPVT.exe exists in the install directory.
        """
        mgr = ChocoManager()
        package_id = winpvt_env["choco_package_id"]
        install_dir: Path = winpvt_env["install_dir"]
        version: str = winpvt_env["version"]

        # Idempotent: uninstall first so the test always starts from a clean state
        if mgr.is_installed(package_id):
            uninstall_result = mgr.uninstall(package_id)
            assert uninstall_result.success, (
                f"Pre-test uninstall failed (exit {uninstall_result.exit_code}):\n"
                f"{uninstall_result.output}"
            )

        # Install
        result = mgr.install(package_id, version)
        assert result.success, (
            f"WinPVT installation failed (exit {result.exit_code}):\n{result.output}"
        )

        # Verify package reported as installed
        assert mgr.is_installed(package_id), (
            "ChocoManager.is_installed() returned False after successful install"
        )

        # Verify each binary exists in the install directory
        for binary in winpvt_env["binaries"]:
            binary_path = install_dir / binary
            assert binary_path.exists(), (
                f"Expected binary not found after install: {binary_path}"
            )

    def test_uninstall(self, winpvt_env, check_environment):
        """
        Uninstall WinPVT and verify the binaries are removed.

        Steps:
            1. Install if not already installed (idempotent setup).
            2. Run ChocoManager.uninstall().
            3. Assert the result is successful.
            4. Assert that WinPVT.exe no longer exists in the install directory.
        """
        mgr = ChocoManager()
        package_id = winpvt_env["choco_package_id"]
        install_dir: Path = winpvt_env["install_dir"]
        version: str = winpvt_env["version"]

        # Idempotent: ensure it is installed before testing uninstall
        if not mgr.is_installed(package_id):
            install_result = mgr.install(package_id, version)
            assert install_result.success, (
                f"Pre-test install failed (exit {install_result.exit_code}):\n"
                f"{install_result.output}"
            )

        # Uninstall
        result = mgr.uninstall(package_id)
        assert result.success, (
            f"WinPVT uninstallation failed (exit {result.exit_code}):\n{result.output}"
        )

        # Verify package reported as not installed
        assert not mgr.is_installed(package_id), (
            "ChocoManager.is_installed() returned True after successful uninstall"
        )

        # Verify the main binary is gone
        for binary in winpvt_env["binaries"]:
            binary_path = install_dir / binary
            assert not binary_path.exists(), (
                f"Binary still exists after uninstall: {binary_path}"
            )
