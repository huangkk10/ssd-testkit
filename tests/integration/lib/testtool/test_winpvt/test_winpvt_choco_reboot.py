"""
WinPVT Chocolatey Install — Reboot-Aware Integration Test

WinPVT installer reboots the machine during installation.  This test uses
RebootManager to:
  1. Save state and write an auto-start script BEFORE triggering the installer.
  2. Verify the installation after the system comes back up.

Run (fresh install + reboot):
    pytest tests/integration/lib/testtool/test_winpvt/test_winpvt_choco_reboot.py -v -s

Recovery (after reboot, auto-started by pytest_auto_run.bat):
    PYTEST_REBOOT_RECOVERY=1 is set by the BAT — RebootManager skips
    test_01 automatically and runs test_02.

Log file:
    tests/integration/lib/testtool/test_winpvt/testlog/winpvt_choco_reboot.log
"""

import logging
import sys
from pathlib import Path

# ── project root ──────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
from framework.reboot_manager import RebootManager
from lib.testtool.choco_manager import ChocoManager

# ── constants ─────────────────────────────────────────────────────────────────
_PACKAGE_ID   = "winpvt"
_VERSION      = "11.16.0"
_INSTALL_DIR  = Path(r"C:\Program Files\Hewlett-Packard\WinPVT 11.16.0")
_BINARY       = "WinPVT.exe"
_LOG_DIR      = Path(__file__).parent / "testlog"
_LOGFILE      = _LOG_DIR / "winpvt_choco_reboot.log"

# ── logging setup ─────────────────────────────────────────────────────────────
def _setup_logging() -> logging.Logger:
    """Configure a logger that writes to both console and a log file."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(_LOGFILE, encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)

    logger = logging.getLogger("test_winpvt_choco_reboot")
    logger.setLevel(logging.DEBUG)
    # Avoid duplicate handlers when pytest re-imports the module
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


_log = _setup_logging()


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def choco_manager() -> ChocoManager:
    return ChocoManager()


# ══════════════════════════════════════════════════════════════════════════════
# Test class
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_winpvt
@pytest.mark.slow
class TestWinPVTChocoInstallReboot:
    """
    Two-phase install verification that survives a system reboot.

    Phase 1 — test_01_install_winpvt
        Prepares recovery state, runs choco install.  If the installer
        reboots the machine before returning, recovery state is already
        saved.  If the installer returns normally (exit 3010 — reboot
        required), this test forces the reboot itself.

    Phase 2 — test_02_verify_post_reboot
        Runs after the machine comes back up.  Checks that WinPVT.exe
        exists in the expected directory and that Chocolatey reports
        the package as installed.
    """

    reboot_mgr: RebootManager

    # ── class-level setup ─────────────────────────────────────────────────────

    @classmethod
    def setup_class(cls):
        cls.reboot_mgr = RebootManager(total_tests=2)
        _log.info("=" * 60)
        _log.info("TestWinPVTChocoInstallReboot  start")
        _log.info("  install_dir : %s", _INSTALL_DIR)
        _log.info("  logfile     : %s", _LOGFILE)
        _log.info("  recovering  : %s", cls.reboot_mgr.state.get("is_recovering"))
        _log.info("  completed   : %s", cls.reboot_mgr.state.get("completed_tests"))
        _log.info("=" * 60)

    @classmethod
    def teardown_class(cls):
        _log.info("TestWinPVTChocoInstallReboot  teardown_class")

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _assert_installer_present() -> None:
        """Fail fast when the WinPVT.exe installer is missing."""
        installer = _ROOT / "bin" / "installers" / "winpvt" / _VERSION / "WinPVT.exe"
        if not installer.is_file():
            pytest.fail(
                f"WinPVT installer not found: {installer}\n"
                "Run tool-manager/prepare_testcase.ps1 to download it."
            )

    @staticmethod
    def _assert_nupkg_present() -> None:
        """Fail fast when the offline nupkg is missing."""
        nupkg = (
            _ROOT / "bin" / "chocolatey" / "packages"
            / _PACKAGE_ID / _VERSION / f"{_PACKAGE_ID}.{_VERSION}.nupkg"
        )
        if not nupkg.is_file():
            pytest.fail(
                f"WinPVT nupkg not found: {nupkg}\n"
                "Run: cd bin/chocolatey/packages/winpvt/11.16.0 && choco pack winpvt.nuspec"
            )

    # ── Phase 1: install ──────────────────────────────────────────────────────

    def test_01_install_winpvt(self, request, choco_manager):
        """Install WinPVT via Chocolatey, then reboot (required by installer)."""
        step = request.node.name

        # Skip if already completed (recovery mode — machine already rebooted)
        if step in self.reboot_mgr.state.get("completed_tests", []):
            _log.info("[test_01] Already completed — skipping (recovery mode)")
            pytest.skip("Already completed before reboot")

        _log.info("[test_01] Checking prerequisites ...")
        self._assert_installer_present()
        self._assert_nupkg_present()

        # ── CRITICAL: save state BEFORE uninstall ─────────────────────────────
        # The WinPVT uninstaller (like the installer) may reboot the machine
        # directly before returning.  We must write the auto-start / recovery
        # script NOW so that if the machine reboots during uninstall, the next
        # run will see completed_tests already containing this step and skip it
        # rather than entering an infinite uninstall-reboot loop.
        _log.info("[test_01] Saving reboot-recovery state before pre-uninstall ...")
        self.reboot_mgr.prepare_for_external_reboot(
            step_name=step,
            test_file=__file__,
        )
        _log.info("[test_01] Auto-start script written.")

        # Uninstall first for a clean idempotent run
        if choco_manager.is_installed(_PACKAGE_ID):
            _log.info("[test_01] WinPVT already installed — uninstalling first ...")
            r = choco_manager.uninstall(_PACKAGE_ID)
            if not r.success:
                _log.warning("[test_01] Pre-test uninstall warning: %s", r.output)

        _log.info("[test_01] Starting install ...")

        # ── Run choco install ─────────────────────────────────────────────────
        result = choco_manager.install(_PACKAGE_ID, _VERSION)

        _log.info(
            "[test_01] choco install exit_code=%s  success=%s",
            result.exit_code, result.success,
        )
        _log.debug("[test_01] choco output:\n%s", result.output)

        if not result.success:
            _log.error("[test_01] Installation failed:\n%s", result.output)
            pytest.fail(
                f"choco install {_PACKAGE_ID} failed (exit {result.exit_code}):\n"
                f"{result.output}"
            )

        # ── If we reach here the installer exited without rebooting ───────────
        # (exit 3010 means "success, reboot required" — force the reboot now)
        _log.info(
            "[test_01] Installer returned — forcing required reboot in 15 s ..."
        )
        self.reboot_mgr.setup_reboot(
            delay=15,
            reason="WinPVT install complete — reboot required",
            test_file=__file__,
        )
        # os._exit(0) is called inside setup_reboot — code below never executes

    # ── Phase 2: verify ───────────────────────────────────────────────────────

    def test_02_verify_post_reboot(self, request, choco_manager):
        """Verify WinPVT is properly installed after the reboot."""
        step = request.node.name
        _log.info("[test_02] Post-reboot verification starting ...")

        # ── 1. Binary on disk ─────────────────────────────────────────────────
        binary_path = _INSTALL_DIR / _BINARY
        _log.info("[test_02] Checking binary: %s", binary_path)
        assert binary_path.exists(), (
            f"WinPVT.exe not found after install: {binary_path}\n"
            "Installation may have failed or installed to a different directory."
        )
        _log.info("[test_02] ✓ Binary found: %s", binary_path)

        # ── 2. Chocolatey package registry ────────────────────────────────────
        is_installed = choco_manager.is_installed(_PACKAGE_ID)
        installed_version = choco_manager.get_installed_version(_PACKAGE_ID)
        _log.info(
            "[test_02] Chocolatey: is_installed=%s  version=%s",
            is_installed, installed_version,
        )
        assert is_installed, (
            "ChocoManager.is_installed('winpvt') returned False after reboot.\n"
            "The package may not have been registered correctly."
        )
        _log.info("[test_02] ✓ Chocolatey reports WinPVT as installed (version %s)", installed_version)

        # ── Mark complete ─────────────────────────────────────────────────────
        self.reboot_mgr.mark_completed(step)
        _log.info("[test_02] Verification PASSED — all checks OK")
        _log.info("[test_02] Log saved to: %s", _LOGFILE)
