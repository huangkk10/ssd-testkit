"""
Integration tests for smicli Chocolatey packaging.

Verifies:
  - choco install smicli  → files copied to C:\\tools\\SmiCli, SMICLI_PATH set
  - choco uninstall smicli → directory removed, SMICLI_PATH cleared

Run:
    pytest -m integration tests/integration/lib/testtool/test_smicli/
    pytest -m "integration and not slow" ...   # fast checks only
"""

import os
import shutil
from pathlib import Path

import pytest

# ── constants ──────────────────────────────────────────────────────────────

TOOL_ID      = "smicli"
CHOCO_VERSION = "2025.11.14"          # version as reported by `choco list`
INSTALL_DIR  = Path(r"C:\tools\SmiCli")
DEST_EXE     = INSTALL_DIR / "SmiCli2.exe"
DRIVER_FILES = ["WinIo64.sys", "WinIoEx.sys"]


# ══════════════════════════════════════════════════════════════════════════
# Group 1 – fast checks (no install required)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_choco
class TestChocoCliAvailability:
    def test_choco_on_path(self):
        assert shutil.which("choco") is not None, (
            "Chocolatey not found on PATH."
        )


@pytest.mark.integration
@pytest.mark.requires_choco
class TestSourceDirectoryStructure:
    """Verify the installer source tree is correctly laid out."""

    def test_version_subfolder_exists(self, smicli_source):
        assert smicli_source.exists(), f"Source dir missing: {smicli_source}"

    def test_exe_present_in_version_folder(self, smicli_source):
        assert (smicli_source / "SmiCli2.exe").exists()

    def test_drivers_present_in_version_folder(self, smicli_source):
        for drv in DRIVER_FILES:
            assert (smicli_source / drv).exists(), f"Driver missing: {drv}"

    def test_not_installed_initially(self, choco_manager):
        """Before any test installs it, the package should be absent."""
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)
        assert choco_manager.is_installed(TOOL_ID) is False


# ══════════════════════════════════════════════════════════════════════════
# Group 2 – install  (slow)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_choco
@pytest.mark.slow
class TestChocoManagerInstall:
    """
    Class-scoped fixture installs smicli once.
    All test methods just read post-install state.
    """

    @pytest.fixture(scope="class", autouse=True)
    def installed_smicli(self, choco_manager, smicli_source):
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)
        # Ensure install dir is clean
        if INSTALL_DIR.exists():
            shutil.rmtree(INSTALL_DIR, ignore_errors=True)

        result = choco_manager.install(TOOL_ID)
        assert result.success, (
            f"Install failed (exit {result.exit_code}):\n{result.output}"
        )

        yield result

        # Teardown
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)

    # ── InstallResult assertions ──────────────────────────────────────────

    def test_install_result_success(self, installed_smicli):
        assert installed_smicli.success is True

    def test_install_result_tool_id(self, installed_smicli):
        assert installed_smicli.tool_id == TOOL_ID

    def test_install_result_exit_code(self, installed_smicli):
        assert installed_smicli.exit_code in (0, 3010)

    def test_install_result_output_not_empty(self, installed_smicli):
        assert installed_smicli.output.strip() != ""

    # ── Post-install file assertions ─────────────────────────────────────

    def test_install_dir_exists(self):
        assert INSTALL_DIR.exists(), f"Install dir missing: {INSTALL_DIR}"

    def test_exe_copied(self):
        assert DEST_EXE.exists(), f"SmiCli2.exe not found: {DEST_EXE}"

    def test_drivers_copied(self):
        for drv in DRIVER_FILES:
            assert (INSTALL_DIR / drv).exists(), f"Driver missing after install: {drv}"

    # ── Post-install choco state ──────────────────────────────────────────

    def test_is_installed_true(self, choco_manager):
        assert choco_manager.is_installed(TOOL_ID) is True

    def test_installed_version_matches(self, choco_manager):
        assert choco_manager.get_installed_version(TOOL_ID) == CHOCO_VERSION

    # ── SMICLI_PATH env var ───────────────────────────────────────────────

    def test_smicli_path_env_var_set(self):
        """SMICLI_PATH machine-level env var must point to SmiCli2.exe."""
        val = os.environ.get("SMICLI_PATH") or \
              __import__("winreg") and _read_machine_env("SMICLI_PATH")
        # Re-read from registry since Machine-level vars need a new process to see
        val = _read_machine_env("SMICLI_PATH")
        assert val is not None, "SMICLI_PATH not set in Machine env"
        assert Path(val).name.lower() == "smicli2.exe"

    def test_smicli_path_points_to_existing_file(self):
        val = _read_machine_env("SMICLI_PATH")
        if val:
            assert Path(val).exists(), f"SMICLI_PATH points to non-existent file: {val}"


# ══════════════════════════════════════════════════════════════════════════
# Group 3 – uninstall  (slow)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_choco
@pytest.mark.slow
class TestChocoManagerUninstall:
    """
    Class-scoped fixture installs then uninstalls smicli once.
    All test methods read post-uninstall state.
    """

    @pytest.fixture(scope="class", autouse=True)
    def uninstall_result(self, choco_manager, smicli_source):
        if not choco_manager.is_installed(TOOL_ID):
            pre = choco_manager.install(TOOL_ID)
            assert pre.success, (
                f"Pre-test install failed (exit {pre.exit_code}):\n{pre.output}"
            )

        result = choco_manager.uninstall(TOOL_ID)

        yield result

        # Safety net
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)

    # ── UninstallResult assertions ────────────────────────────────────────

    def test_uninstall_result_success(self, uninstall_result):
        assert uninstall_result.success is True

    def test_uninstall_result_exit_code(self, uninstall_result):
        assert uninstall_result.exit_code in (0, 3010)

    # ── Post-uninstall file assertions ────────────────────────────────────

    def test_install_dir_removed(self):
        assert not INSTALL_DIR.exists(), f"Install dir still present: {INSTALL_DIR}"

    def test_exe_gone(self):
        assert not DEST_EXE.exists()

    # ── Post-uninstall choco state ────────────────────────────────────────

    def test_is_installed_false(self, choco_manager):
        assert choco_manager.is_installed(TOOL_ID) is False

    def test_installed_version_none(self, choco_manager):
        assert choco_manager.get_installed_version(TOOL_ID) is None

    # ── SMICLI_PATH env var cleared ───────────────────────────────────────

    def test_smicli_path_env_var_cleared(self):
        val = _read_machine_env("SMICLI_PATH")
        assert val is None or val == "", (
            f"SMICLI_PATH should be cleared after uninstall, got: {val}"
        )


# ── helpers ────────────────────────────────────────────────────────────────

def _read_machine_env(name: str):
    """Read a Machine-scope environment variable directly from the registry."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        )
        try:
            value, _ = winreg.QueryValueEx(key, name)
            return value
        except FileNotFoundError:
            return None
        finally:
            winreg.CloseKey(key)
    except Exception:
        return None
