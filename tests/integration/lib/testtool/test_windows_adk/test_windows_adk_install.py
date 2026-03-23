"""
Windows ADK Install / Uninstall Integration Tests

Verifies that Windows ADK can be installed and uninstalled through
ChocoManager, and that the expected binaries are present after
installation and absent after uninstallation.

Requirements:
    - Chocolatey must be installed on the test machine.
    - The offline nupkg must exist under
      bin/chocolatey/packages/windows-adk/<version>/

Run:
    pytest tests/integration/lib/testtool/test_windows_adk/ -v
"""

import pytest
from pathlib import Path

from lib.testtool.choco_manager import ChocoManager


@pytest.mark.integration
@pytest.mark.requires_windows_adk
@pytest.mark.slow
class TestWindowsADKInstallation:
    """Tests for Windows ADK installation via Chocolatey."""

    def test_install(self, adk_env, check_environment):
        """
        Install Windows ADK and verify the expected binaries are present.

        Steps:
            1. Uninstall if already installed (idempotent setup).
            2. Run ChocoManager.install().
            3. Assert the result is successful.
            4. Assert each expected binary exists in the install directory.
        """
        mgr = ChocoManager()
        package_id = adk_env["choco_package_id"]
        install_dir: Path = adk_env["install_dir"]

        # Idempotent: uninstall first so the test always starts from a clean state
        if mgr.is_installed(package_id):
            uninstall_result = mgr.uninstall(package_id)
            assert uninstall_result.success, (
                f"Pre-test uninstall failed (exit {uninstall_result.exit_code}):\n"
                f"{uninstall_result.output}"
            )

        # Install
        result = mgr.install(package_id, adk_env["version"])
        assert result.success, (
            f"Installation failed (exit {result.exit_code}):\n{result.output}"
        )

        # Verify package reported as installed
        assert mgr.is_installed(package_id), (
            "ChocoManager.is_installed() returned False after successful install"
        )

        # Verify each binary exists in the install directory
        for binary in adk_env["binaries"]:
            binary_path = install_dir / binary
            assert binary_path.exists(), (
                f"Expected binary not found after install: {binary_path}"
            )

    def test_uninstall(self, adk_env, check_environment):
        """
        Uninstall Windows ADK and verify the binaries are removed.

        Steps:
            1. Install if not already installed (idempotent setup).
            2. Run ChocoManager.uninstall().
            3. Assert the result is successful.
            4. Assert that the install directory no longer contains the ADK binaries.
        """
        mgr = ChocoManager()
        package_id = adk_env["choco_package_id"]
        install_dir: Path = adk_env["install_dir"]

        # Idempotent: ensure it is installed before testing uninstall
        if not mgr.is_installed(package_id):
            install_result = mgr.install(package_id, adk_env["version"])
            assert install_result.success, (
                f"Pre-test install failed (exit {install_result.exit_code}):\n"
                f"{install_result.output}"
            )

        # Uninstall
        result = mgr.uninstall(package_id)
        assert result.success, (
            f"Uninstallation failed (exit {result.exit_code}):\n{result.output}"
        )

        # Verify package reported as not installed
        assert not mgr.is_installed(package_id), (
            "ChocoManager.is_installed() returned True after successful uninstall"
        )

        # Verify binaries are no longer present
        for binary in adk_env["binaries"]:
            binary_path = install_dir / binary
            assert not binary_path.exists(), (
                f"Binary still present after uninstall: {binary_path}"
            )

    def test_install_then_uninstall(self, adk_env, check_environment):
        """
        End-to-end cycle: install Windows ADK, verify binaries, then uninstall,
        and verify cleanup.

        This test exercises the full lifecycle in a single test to catch any
        ordering or state issues.
        """
        mgr = ChocoManager()
        package_id = adk_env["choco_package_id"]
        install_dir: Path = adk_env["install_dir"]

        # --- Install ---
        if mgr.is_installed(package_id):
            mgr.uninstall(package_id)

        install_result = mgr.install(package_id, adk_env["version"])
        assert install_result.success, (
            f"Install failed (exit {install_result.exit_code}):\n{install_result.output}"
        )
        assert mgr.is_installed(package_id), "Package not detected as installed after install"

        for binary in adk_env["binaries"]:
            assert (install_dir / binary).exists(), (
                f"Missing binary after install: {binary}"
            )

        # --- Uninstall ---
        uninstall_result = mgr.uninstall(package_id)
        assert uninstall_result.success, (
            f"Uninstall failed (exit {uninstall_result.exit_code}):\n{uninstall_result.output}"
        )
        assert not mgr.is_installed(package_id), (
            "Package still detected as installed after uninstall"
        )

        for binary in adk_env["binaries"]:
            assert not (install_dir / binary).exists(), (
                f"Binary still present after uninstall: {binary}"
            )

    def test_install_version_reported(self, adk_env, check_environment):
        """
        After installation, ChocoManager.get_installed_version() must return
        a non-empty string.
        """
        mgr = ChocoManager()
        package_id = adk_env["choco_package_id"]

        if not mgr.is_installed(package_id):
            install_result = mgr.install(package_id, adk_env["version"])
            assert install_result.success, (
                f"Pre-test install failed:\n{install_result.output}"
            )

        version = mgr.get_installed_version(package_id)
        assert version is not None and version != "", (
            "get_installed_version() returned empty result for an installed package"
        )
