"""
Integration tests for lib/testtool/choco_manager.py

These tests call the real Chocolatey CLI and (for the slow group) run the
actual ADK installer.  They are intentionally NOT part of the normal test run.

Run:
    pytest -m integration tests/integration/lib/testtool/test_choco_manager/

Run only the fast (no-install) subset:
    pytest -m "integration and not slow" tests/integration/lib/testtool/test_choco_manager/
"""

import shutil
from pathlib import Path

import pytest

# ── constants ──────────────────────────────────────────────────────────────

TOOL_ID = "windows-adk"
# Version as stored in package_meta.yaml (raw build number)
META_VERSION = "22621"
# Version as reported by `choco list` after install (NuGet X.Y.Z normalisation)
CHOCO_VERSION = "22621.0.0"

# Well-known binary that adksetup.exe places on disk when WPT is selected
WPR_EXE = Path(r"C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\wpr.exe")


# ══════════════════════════════════════════════════════════════════════════
# Group 1 – fast read-only checks (no ADK install required)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_choco
class TestChocoCliAvailability:
    """Verify that Chocolatey is on PATH and callable before any other test."""

    def test_choco_on_path(self):
        """choco.exe must be discoverable via PATH."""
        assert shutil.which("choco") is not None, (
            "Chocolatey not found on PATH. "
            "Install it first by running bin/chocolatey/scripts/install_choco.ps1"
        )


@pytest.mark.integration
@pytest.mark.requires_choco
class TestIsInstalledWhenNotInstalled:
    """
    Verify query methods return sensible defaults when windows-adk is absent.

    The autouse fixture guarantees a clean (not-installed) state.
    It also uninstalls after the tests to leave the machine clean.
    """

    @pytest.fixture(autouse=True)
    def ensure_not_installed(self, choco_manager):
        """Uninstall windows-adk before (and after) this test class."""
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)
        yield
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)

    def test_is_installed_returns_false(self, choco_manager):
        assert choco_manager.is_installed(TOOL_ID) is False

    def test_get_installed_version_returns_none(self, choco_manager):
        assert choco_manager.get_installed_version(TOOL_ID) is None


# ══════════════════════════════════════════════════════════════════════════
# Group 2 – install operation  (slow, requires adksetup.exe)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_choco
@pytest.mark.slow
class TestChocoManagerInstall:
    """
    End-to-end install tests.

    A class-scoped fixture installs windows-adk *once* for the whole class,
    then uninstalls it in teardown.  Individual test methods only read state –
    they do NOT call install/uninstall themselves.
    """

    @pytest.fixture(scope="class", autouse=True)
    def installed_adk(self, choco_manager, adk_installer_path):  # noqa: F811
        """Install windows-adk once for all tests in this class."""
        # Ensure clean slate
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)

        result = choco_manager.install(TOOL_ID)
        assert result.success, (
            f"Pre-test install failed (exit {result.exit_code}):\n{result.output}"
        )

        yield result  # tests receive the InstallResult

        # Teardown: leave the machine in a clean state
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)

    # ── InstallResult field assertions ────────────────────────────────────

    def test_install_result_success_flag(self, installed_adk):
        assert installed_adk.success is True

    def test_install_result_tool_id(self, installed_adk):
        assert installed_adk.tool_id == TOOL_ID

    def test_install_result_version(self, installed_adk):
        assert installed_adk.version == META_VERSION

    def test_install_result_exit_code_acceptable(self, installed_adk):
        # 0 = success, 3010 = success + reboot pending
        assert installed_adk.exit_code in (0, 3010), (
            f"Unexpected exit code: {installed_adk.exit_code}"
        )

    def test_install_result_output_not_empty(self, installed_adk):
        assert installed_adk.output.strip() != ""

    # ── Post-install state assertions ─────────────────────────────────────

    def test_is_installed_returns_true_after_install(self, choco_manager):
        assert choco_manager.is_installed(TOOL_ID) is True

    def test_get_installed_version_matches_default(self, choco_manager):
        assert choco_manager.get_installed_version(TOOL_ID) == CHOCO_VERSION

    def test_wpr_exe_present_after_install(self):
        assert WPR_EXE.exists(), (
            f"wpr.exe not found at {WPR_EXE} – ADK WPT component may not have installed"
        )


# ══════════════════════════════════════════════════════════════════════════
# Group 3 – uninstall operation  (slow, requires adksetup.exe)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_choco
@pytest.mark.slow
class TestChocoManagerUninstall:
    """
    End-to-end uninstall tests.

    A class-scoped fixture installs windows-adk, calls uninstall *once*, then
    yields the InstallResult.  All test methods receive the same result object
    and only read post-uninstall state – they never call uninstall themselves.
    This avoids choco exit-code 1 ("not installed") on repeated calls.
    """

    @pytest.fixture(scope="class", autouse=True)
    def uninstall_result(self, choco_manager, adk_installer_path):  # noqa: F811
        """Install windows-adk, perform a single uninstall, yield the result."""
        if not choco_manager.is_installed(TOOL_ID):
            pre = choco_manager.install(TOOL_ID)
            assert pre.success, (
                f"Pre-test install failed (exit {pre.exit_code}):\n{pre.output}"
            )

        result = choco_manager.uninstall(TOOL_ID)

        yield result  # tests receive the single InstallResult

        # Safety net: remove if somehow still installed
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)

    # ── UninstallResult field assertions ──────────────────────────────────

    def test_uninstall_result_success_flag(self, uninstall_result):
        assert uninstall_result.success is True

    def test_uninstall_result_exit_code_acceptable(self, uninstall_result):
        assert uninstall_result.exit_code in (0, 3010), (
            f"Unexpected exit code: {uninstall_result.exit_code}"
        )

    # ── Post-uninstall state assertions ───────────────────────────────────

    def test_is_installed_returns_false_after_uninstall(self, choco_manager):
        assert choco_manager.is_installed(TOOL_ID) is False

    def test_get_installed_version_returns_none_after_uninstall(self, choco_manager):
        assert choco_manager.get_installed_version(TOOL_ID) is None

    def test_wpr_exe_gone_after_uninstall(self):
        assert not WPR_EXE.exists(), (
            f"wpr.exe still present at {WPR_EXE} after uninstall"
        )
