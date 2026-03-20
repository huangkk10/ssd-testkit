"""
Integration tests for playwright-browsers Chocolatey packaging.

Verifies:
  - choco install playwright-browsers  → browsers copied to C:\\tools\\playwright-browsers,
                                         PLAYWRIGHT_BROWSERS_PATH set
  - choco uninstall playwright-browsers → directory removed, env var cleared

Run:
    pytest -m integration tests/integration/lib/testtool/test_playwright_browsers/
    pytest -m "integration and not slow" ...   # fast checks only
"""

import os
import shutil
import winreg
from pathlib import Path

import pytest

# ── constants ──────────────────────────────────────────────────────────────

TOOL_ID      = "playwright-browsers"
CHOCO_VERSION = "1.58.0"
INSTALL_DIR  = Path(r"C:\tools\playwright-browsers")
DEST_CHROME  = INSTALL_DIR / "chromium-1208" / "chrome-win64" / "chrome.exe"
BROWSER_BUILDS = [
    "chromium-1208",
    "chromium_headless_shell-1208",
    "ffmpeg-1011",
    "winldd-1007",
]


def _read_machine_env(name: str):
    """Read a Machine-scope env var directly from registry (visible immediately)."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        )
        value, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return value
    except FileNotFoundError:
        return None


# ══════════════════════════════════════════════════════════════════════════
# Group 1 – fast checks (no install required)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_choco
class TestChocoCliAvailability:
    def test_choco_on_path(self):
        assert shutil.which("choco") is not None, "Chocolatey not found on PATH."


@pytest.mark.integration
@pytest.mark.requires_choco
class TestSourceDirectoryStructure:
    """Verify the installer source tree is correctly laid out."""

    def test_version_subfolder_exists(self, browsers_source):
        assert browsers_source.exists(), f"Source dir missing: {browsers_source}"

    def test_chromium_exe_present(self, browsers_source):
        chrome = browsers_source / "chromium-1208" / "chrome-win64" / "chrome.exe"
        assert chrome.exists(), f"chrome.exe not found: {chrome}"

    def test_all_browser_builds_present(self, browsers_source):
        for build in BROWSER_BUILDS:
            assert (browsers_source / build).exists(), f"Browser build missing: {build}"

    def test_not_installed_initially(self, choco_manager):
        """Before install tests, ensure package is absent."""
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)
        assert choco_manager.is_installed(TOOL_ID) is False


# ══════════════════════════════════════════════════════════════════════════
# Group 2 – install  (slow)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_choco
@pytest.mark.requires_playwright_browsers
@pytest.mark.slow
class TestChocoManagerInstall:
    """Class-scoped fixture installs playwright-browsers once; all methods read post-install state."""

    @pytest.fixture(scope="class", autouse=True)
    def installed(self, choco_manager, browsers_source):
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)
        if INSTALL_DIR.exists():
            shutil.rmtree(INSTALL_DIR, ignore_errors=True)

        result = choco_manager.install(TOOL_ID)
        assert result.success, f"Install failed (exit {result.exit_code}):\n{result.output}"
        yield result

        # Teardown
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)

    def test_install_result_success(self, installed):
        assert installed.success is True

    def test_install_result_tool_id(self, installed):
        assert installed.tool_id == TOOL_ID

    def test_install_dir_exists(self):
        assert INSTALL_DIR.exists(), f"Install dir missing: {INSTALL_DIR}"

    def test_chrome_exe_exists(self):
        assert DEST_CHROME.exists(), f"chrome.exe missing: {DEST_CHROME}"

    def test_all_browser_builds_copied(self):
        for build in BROWSER_BUILDS:
            assert (INSTALL_DIR / build).exists(), f"Browser build missing after install: {build}"

    def test_is_installed(self, choco_manager):
        assert choco_manager.is_installed(TOOL_ID)

    def test_playwright_browsers_path_env_var_set(self):
        """PLAYWRIGHT_BROWSERS_PATH must be set at Machine scope in registry."""
        value = _read_machine_env("PLAYWRIGHT_BROWSERS_PATH")
        assert value is not None, "PLAYWRIGHT_BROWSERS_PATH not found in Machine registry"
        assert value == str(INSTALL_DIR), (
            f"PLAYWRIGHT_BROWSERS_PATH = '{value}', expected '{INSTALL_DIR}'"
        )


# ══════════════════════════════════════════════════════════════════════════
# Group 3 – uninstall  (slow)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_choco
@pytest.mark.requires_playwright_browsers
@pytest.mark.slow
class TestChocoManagerUninstall:
    """Class-scoped fixture installs then immediately uninstalls; all methods read post-uninstall state."""

    @pytest.fixture(scope="class", autouse=True)
    def uninstalled(self, choco_manager, browsers_source):
        if not choco_manager.is_installed(TOOL_ID):
            r = choco_manager.install(TOOL_ID)
            assert r.success, f"Pre-uninstall install failed:\n{r.output}"

        result = choco_manager.uninstall(TOOL_ID)
        assert result.success, f"Uninstall failed (exit {result.exit_code}):\n{result.output}"
        yield result

    def test_uninstall_result_success(self, uninstalled):
        assert uninstalled.success is True

    def test_install_dir_removed(self):
        assert not INSTALL_DIR.exists(), f"Install dir still present: {INSTALL_DIR}"

    def test_not_installed(self, choco_manager):
        assert not choco_manager.is_installed(TOOL_ID)

    def test_playwright_browsers_path_env_var_cleared(self):
        """PLAYWRIGHT_BROWSERS_PATH must be removed from Machine registry after uninstall."""
        value = _read_machine_env("PLAYWRIGHT_BROWSERS_PATH")
        assert value is None, (
            f"PLAYWRIGHT_BROWSERS_PATH still set after uninstall: '{value}'"
        )
